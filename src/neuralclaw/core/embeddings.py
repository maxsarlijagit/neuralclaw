"""Ollama embeddings integration for semantic search."""

import math
from typing import Optional

import requests

from neuralclaw.config import load_config


class OllamaEmbeddings:
    """Ollama embeddings client for semantic search."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
    ):
        config = load_config()
        self.base_url = base_url or config.ollama_base_url
        self.model = model or config.embeddings_model
        self.timeout = timeout

    def is_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self) -> list[str]:
        """List available models."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
            return []
        except requests.RequestException:
            return []

    def model_exists(self) -> bool:
        """Check if the configured model is available."""
        return self.model in self.list_models()

    def pull_model(self, timeout: int = 300) -> bool:
        """Pull the configured model from Ollama registry."""
        try:
            import threading
            import queue

            result_queue = queue.Queue()

            def pull():
                try:
                    resp = requests.post(
                        f"{self.base_url}/api/pull",
                        json={"name": self.model},
                        timeout=timeout,
                        stream=True,
                    )
                    for chunk in resp.iter_lines():
                        if chunk:
                            data = chunk.decode()
                            if "error" in data.lower():
                                result_queue.put(False)
                                return
                    result_queue.put(True)
                except requests.RequestException:
                    result_queue.put(False)

            t = threading.Thread(target=pull)
            t.start()
            t.join(timeout=timeout + 10)
            if t.is_alive():
                return False
            try:
                return result_queue.get_nowait()
            except:
                return False
        except Exception:
            return False

    def embed(self, text: str) -> Optional[list[float]]:
        """Compute embedding for a single text."""
        try:
            resp = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                return resp.json().get("embedding")
            return None
        except requests.RequestException:
            return None

    def embed_batch(self, texts: list[str]) -> Optional[list[list[float]]]:
        """Compute embeddings for multiple texts."""
        if not texts:
            return []
        try:
            resp = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": texts[0]},
                timeout=self.timeout,
            )
            # Ollama single embedding at a time for now
            results = []
            for text in texts:
                emb = self.embed(text)
                if emb:
                    results.append(emb)
                else:
                    results.append([0.0] * 768)  # fallback zero vector
            return results
        except requests.RequestException:
            return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def get_embeddings_client() -> Optional[OllamaEmbeddings]:
    """Get an Ollama embeddings client if Ollama is available."""
    client = OllamaEmbeddings()
    if client.is_available():
        return client
    return None