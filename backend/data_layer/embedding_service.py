"""Embedding generation service using sentence-transformers."""

from sentence_transformers import SentenceTransformer
from typing import Optional


class EmbeddingService:
    """Generates vector embeddings for text chunks and claims."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize the embedding model.

        Args:
            model_name: Name of the sentence-transformer model.
        """
        self._model_name = model_name
        self._model: Optional[SentenceTransformer] = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load the embedding model."""
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed.

        Returns:
            List of floats representing the embedding vector.
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors.
        """
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
