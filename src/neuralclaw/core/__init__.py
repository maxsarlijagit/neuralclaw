"""Core modules."""

from neuralclaw.core.context import (
    add_context_item,
    search_context,
    get_context_item,
    update_context_item_state,
    delete_context_item,
    count_context_items,
)
from neuralclaw.core.vault import (
    vault_set,
    vault_get,
    vault_list,
    vault_delete,
    vault_exists,
    init_vault,
)
from neuralclaw.core.projects import (
    create_project,
    list_projects,
    get_project,
    archive_project,
    delete_project,
    project_exists,
)
from neuralclaw.core.bridge import (
    load_adapter,
    build_context_export,
    export_context_json,
    ADAPTERS_DIR,
)

__all__ = [
    "add_context_item",
    "search_context",
    "get_context_item",
    "update_context_item_state",
    "delete_context_item",
    "count_context_items",
    "vault_set",
    "vault_get",
    "vault_list",
    "vault_delete",
    "vault_exists",
    "init_vault",
    "create_project",
    "list_projects",
    "get_project",
    "archive_project",
    "delete_project",
    "project_exists",
    "load_adapter",
    "build_context_export",
    "export_context_json",
    "ADAPTERS_DIR",
]
