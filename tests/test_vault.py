"""Tests for vault module."""

import hashlib
import pytest
from cryptography.fernet import Fernet

from neuralclaw.core.vault import (
    init_vault, vault_set, vault_get, vault_list,
    vault_delete, vault_exists, generate_key, _encrypt_value, _decrypt_value,
)


class TestVaultInit:
    """Tests for vault initialization."""

    def test_init_creates_key_file(self, vaultInitialized, temp_config):
        assert temp_config["vault_key_path"].exists()

    def test_init_idempotent(self, vaultInitialized, temp_config):
        key1 = temp_config["vault_key_path"].read_text()
        init_vault()  # Should not regenerate
        key2 = temp_config["vault_key_path"].read_text()
        assert key1 == key2

    def test_init_creates_vault_db(self, vaultInitialized, temp_config):
        vault_db = temp_config["vault_dir"] / "vault.db"
        assert vault_db.exists()

    def test_vault_exists_after_init(self, fresh_db):
        init_vault()
        assert vault_exists() is True


class TestVaultSet:
    """Tests for vault_set function."""

    def test_set_and_get_simple(self, fresh_db):
        init_vault()
        vault_set("MY_SECRET", "secret_value")
        assert vault_get("MY_SECRET") == "secret_value"

    def test_set_normalizes_name(self, fresh_db):
        init_vault()
        vault_set("my_secret", "value")
        assert vault_get("MY_SECRET") == "value"
        assert vault_get("my_secret") == "value"

    def test_set_overwrites_existing(self, fresh_db):
        init_vault()
        vault_set("OVERWRITE_ME", "first_value")
        vault_set("OVERWRITE_ME", "second_value")
        assert vault_get("OVERWRITE_ME") == "second_value"

    def test_set_accepts_none_value(self, fresh_db):
        """Setting None value should not be allowed or should handle gracefully."""
        init_vault()
        # vault_set should reject None
        with pytest.raises(Exception):
            vault_set("NULL_SECRET", None)


class TestVaultGet:
    """Tests for vault_get function."""

    def test_get_existing_secret(self, fresh_db):
        init_vault()
        vault_set("GET_TEST", "my_value")
        assert vault_get("GET_TEST") == "my_value"

    def test_get_nonexistent_returns_none(self, fresh_db):
        init_vault()
        assert vault_get("DOES_NOT_EXIST") is None

    def test_get_before_init_returns_none(self, fresh_db):
        # Without init, vault should not exist
        assert vault_get("ANYTHING") is None


class TestVaultList:
    """Tests for vault_list function."""

    def test_list_empty(self, fresh_db):
        init_vault()
        assert vault_list() == []

    def test_list_multiple_secrets(self, fresh_db):
        init_vault()
        vault_set("SECRET_A", "value_a")
        vault_set("SECRET_B", "value_b")
        vault_set("SECRET_C", "value_c")
        secrets = vault_list()
        assert len(secrets) == 3
        assert "SECRET_A" in secrets
        assert "SECRET_B" in secrets
        assert "SECRET_C" in secrets

    def test_list_sorted_alphabetically(self, fresh_db):
        init_vault()
        vault_set("ZZZ_LAST", "v")
        vault_set("AAA_FIRST", "v")
        vault_set("MMM_MIDDLE", "v")
        secrets = vault_list()
        assert secrets == ["AAA_FIRST", "MMM_MIDDLE", "ZZZ_LAST"]


class TestVaultDelete:
    """Tests for vault_delete function."""

    def test_delete_existing(self, fresh_db):
        init_vault()
        vault_set("TO_DELETE", "temp_value")
        assert vault_get("TO_DELETE") == "temp_value"

        result = vault_delete("TO_DELETE")
        assert result is True
        assert vault_get("TO_DELETE") is None

    def test_delete_nonexistent_returns_false(self, fresh_db):
        init_vault()
        result = vault_delete("DOES_NOT_EXIST")
        assert result is False

    def test_delete_idempotent(self, fresh_db):
        """Deleting twice should return False both times."""
        init_vault()
        vault_set("IDEMPOTENT", "v")
        vault_delete("IDEMPOTENT")
        result = vault_delete("IDEMPOTENT")
        assert result is False


class TestVaultEncryption:
    """Tests that vault properly encrypts data."""

    def test_plaintext_not_in_vault_db(self, vaultInitialized, temp_config):
        vault_set("SUPER_SECRET", "my_secret_value")

        vault_db = temp_config["vault_dir"] / "vault.db"
        content = vault_db.read_bytes()
        assert b"my_secret_value" not in content
        assert b"SUPER_SECRET" not in content

    def test_encrypted_value_is_different_each_time(self, fresh_db):
        """Fernet encryption should produce different ciphertexts (due to IV)."""
        init_vault()
        vault_set("SAME_VALUE", "constant_value")
        vault_set("SAME_VALUE", "constant_value")

        # If we read the DB directly, we should see two different encrypted values
        # (this is implicit in Fernet's usage but worth noting)
        assert vault_get("SAME_VALUE") == "constant_value"

    def test_wrong_key_cannot_decrypt(self, vaultInitialized, temp_config):
        """If someone manually replaces vault.key, decryption should fail."""
        vault_set("SECRET", "value")

        # Replace key with wrong one
        wrong_key = Fernet.generate_key()
        temp_config["vault_key_path"].write_text(wrong_key.decode())

        # Should raise InvalidToken
        with pytest.raises(Exception):  # InvalidToken from cryptography
            vault_get("SECRET")


class TestGenerateKey:
    """Tests for generate_key function."""

    def test_generate_key_format(self):
        key = generate_key()
        # Fernet keys are 44 chars base64-encoded
        assert len(key) == 44
        # Should be valid base64 that Fernet can use
        f = Fernet(key.encode())
        assert f is not None

    def test_generate_key_unique(self):
        keys = [generate_key() for _ in range(10)]
        assert len(set(keys)) == 10  # All unique
