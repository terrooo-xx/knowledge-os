"""Embedding provider adapters: OpenAI and BGE."""
from __future__ import annotations

import os


class EmbeddingError(RuntimeError):
    pass


class OpenAIEmbedder:
    def __init__(self, model: str, api_key_env: str):
        self.model = model
        self.api_key_env = api_key_env

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise EmbeddingError("openai package is required") from exc
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise EmbeddingError(f"missing environment variable {self.api_key_env}")
        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]


class BgeEmbedder:
    def __init__(self, model: str):
        self.model_name = model
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise EmbeddingError("sentence-transformers is required") from exc
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._get_model().encode(texts, normalize_embeddings=True)
        return vectors.tolist()


def create_embedder(cfg: dict):
    provider = cfg["embedding"]["provider"]
    if provider == "openai":
        return OpenAIEmbedder(
            cfg["embedding"]["model"], cfg["embedding"]["api_key_env"]
        )
    if provider == "bge":
        return BgeEmbedder(cfg["embedding"]["model"])
    raise EmbeddingError(f"unsupported embedding provider: {provider}")
