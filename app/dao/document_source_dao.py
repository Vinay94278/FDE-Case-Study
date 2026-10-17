"""Document source DAO: where the documentation comes from.

Today: a JSON file (the seed data). Tomorrow: the Solstice docs site, a CMS export,
SharePoint, or a folder of PDFs converted with MarkItDown. Each is one new class
registered under a name and selected with DOCUMENT_SOURCE=<name>.
"""
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from app.core.component_registry import ComponentRegistry
from app.core.exceptions import DocumentLoadException
from app.core.settings import Settings
from app.models.corpus_models import Document

logger = logging.getLogger(__name__)

DOCUMENT_SOURCE_REGISTRY = ComponentRegistry("document source")

REQUIRED_DOCUMENT_FIELDS = ("doc_id", "title", "content")


class DocumentSourceDAO(ABC):
    """Reads raw documentation articles from a source system."""

    @abstractmethod
    def load_documents(self) -> List[Document]:
        """Return every article. Raise DocumentLoadException if the source cannot be read."""

    @abstractmethod
    def get_source_name(self) -> str:
        """Short name shown in /health and logs."""


class JsonFileDocumentSourceDAO(DocumentSourceDAO):
    """Reads {"docs": [{"doc_id", "title", "content"}, ...]} from a JSON file."""

    def __init__(self, file_path: Path):
        self.file_path = file_path

    def get_source_name(self) -> str:
        return "json:" + self.file_path.name

    def load_documents(self) -> List[Document]:
        raw_data = self._read_json_file()
        raw_documents = raw_data.get("docs")
        if not isinstance(raw_documents, list):
            raise DocumentLoadException(
                technical_message="'docs' list missing in " + str(self.file_path)
            )

        documents = []
        seen_doc_ids = set()
        for position, raw_document in enumerate(raw_documents):
            document = self._to_document(raw_document, position)
            if document.doc_id in seen_doc_ids:
                raise DocumentLoadException(
                    technical_message="Duplicate doc_id '" + document.doc_id + "' in " + str(self.file_path)
                )
            seen_doc_ids.add(document.doc_id)
            documents.append(document)

        logger.info("Loaded %d documents from %s", len(documents), self.file_path.name)
        return documents

    def _read_json_file(self) -> dict:
        try:
            with open(self.file_path, encoding="utf-8") as json_file:
                return json.load(json_file)
        except FileNotFoundError as error:
            raise DocumentLoadException(
                technical_message="Docs file not found: " + str(self.file_path)
            ) from error
        except json.JSONDecodeError as error:
            raise DocumentLoadException(
                technical_message="Docs file is not valid JSON: " + str(error)
            ) from error
        except OSError as error:
            raise DocumentLoadException(
                technical_message="Docs file could not be read: " + str(error)
            ) from error

    def _to_document(self, raw_document: dict, position: int) -> Document:
        if not isinstance(raw_document, dict):
            raise DocumentLoadException(
                technical_message="Document at position " + str(position) + " is not an object"
            )
        for field_name in REQUIRED_DOCUMENT_FIELDS:
            field_value = raw_document.get(field_name)
            if not isinstance(field_value, str) or field_value.strip() == "":
                raise DocumentLoadException(
                    technical_message=(
                        "Document at position " + str(position)
                        + " has a missing or empty '" + field_name + "' field"
                    )
                )
        return Document(
            doc_id=raw_document["doc_id"].strip(),
            title=raw_document["title"].strip(),
            content=raw_document["content"].strip(),
            source_name=self.get_source_name(),
        )


@DOCUMENT_SOURCE_REGISTRY.register("json")
def build_json_file_document_source(settings: Settings) -> DocumentSourceDAO:
    return JsonFileDocumentSourceDAO(settings.docs_path)
