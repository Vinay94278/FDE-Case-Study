"""Optional sentence-embedding model.

If sentence-transformers is not installed, or the model cannot be downloaded, the
service keeps working with keyword search only and reports that in /health.
"""
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class EmbeddingModel:
    def __init__(self, model_name: str, is_enabled: bool):
        self.model_name = model_name
        self.is_available = False
        self.status_description = "disabled by config"
        self._model = None

        if not is_enabled:
            return

        try:
            from sentence_transformers import SentenceTransformer  # optional dependency
            self._model = SentenceTransformer(model_name)
            self.is_available = True
            self.status_description = "on (" + model_name + ")"
        except ImportError:
            self.status_description = "unavailable: sentence-transformers not installed, using keyword search only"
            logger.warning("Embeddings %s", self.status_description)
        except Exception as error:  # model download or load failure must not stop the service
            self.status_description = "unavailable: " + type(error).__name__ + ", using keyword search only"
            logger.warning("Embeddings %s (%s)", self.status_description, error)

    def encode(self, texts: List[str]) -> Optional[object]:
        """Return a normalised matrix (one row per text), or None when embeddings are off."""
        if not self.is_available:
            return None
        return self._model.encode(texts, normalize_embeddings=True)
