from __future__ import annotations

from typing import Any, cast

import structlog

logger = structlog.get_logger()

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

_model_cache: dict[str, Any] = {}


def warm_up() -> None:
    """Pre-load the embedding model (called at startup)."""
    _get_model()


def _get_model() -> Any:
    """Get or lazily initialize the embedding model."""
    if "model" not in _model_cache:
        from fastembed import TextEmbedding  # type: ignore[import-untyped]

        logger.info("Loading embedding model", model=EMBEDDING_MODEL)
        _model_cache["model"] = TextEmbedding(EMBEDDING_MODEL)
        logger.info("Embedding model loaded", model=EMBEDDING_MODEL)
    return cast(Any, _model_cache["model"])


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts, returning a list of float vectors."""
    model = _get_model()
    results = list(model.embed(texts))
    return [cast(list[float], e.tolist()) for e in results]


def embed_query(query: str) -> list[float]:
    """Embed a single query string."""
    model = _get_model()
    results = list(model.query_embed(query))
    return cast(list[float], results[0].tolist())
