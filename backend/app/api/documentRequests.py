"""
EPIC — The request bodies the documents API accepts (app/api/documents.py), with the bounds each field is held to.
"""
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, Field, field_validator

from app.services.llm_service import GENERATED_DOC_TYPES

MAX_DRAFT_DESCRIPTION_CHARS = 4000
MAX_DRAFT_TITLE_CHARS = 200
MAX_DRAFT_SECTION_CHARS = 20000
MAX_DRAFT_SECTIONS = 20
# A saved draft is written by a model, not measured or inspected; prompts are told so (promptSafety.SOURCE_ID_RULES).
AI_DRAFT_ORIGIN = "ai_draft"


def _require_generated_doc_type(value: str) -> str:
    # An unknown type must fail loudly: the generator would otherwise fall back to the
    # maintenance-record template and hand back a draft of the wrong kind of document.
    if value not in GENERATED_DOC_TYPES:
        raise ValueError(f"doc_type must be one of: {', '.join(GENERATED_DOC_TYPES)}")
    return value


GeneratedDocType = Annotated[str, AfterValidator(_require_generated_doc_type)]


class DocumentNameUpdate(BaseModel):
    name: str


class GenerateDocumentRequest(BaseModel):
    doc_type: GeneratedDocType
    equipment_id: str
    description: str = Field(max_length=MAX_DRAFT_DESCRIPTION_CHARS)  # user's natural language context
    extra_fields: dict = {}    # optional type-specific hints, such as the technician or the date

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("description must not be empty")
        return v.strip()


class SaveGeneratedDocumentRequest(BaseModel):
    """An AI draft as the browser saves it; its sections become retrievable text, so their size is bounded."""

    doc_type: GeneratedDocType
    equipment_id: str
    title: str = Field(min_length=1, max_length=MAX_DRAFT_TITLE_CHARS)
    sections: dict[str, Annotated[str, Field(max_length=MAX_DRAFT_SECTION_CHARS)]] = Field(
        max_length=MAX_DRAFT_SECTIONS,
    )
    entities: dict[str, Any] = {}  # equipment_ids, people, regulations, summary …
