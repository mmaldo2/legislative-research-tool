"""Schemas for policy workspace composer endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.schemas.common import MetaResponse


class PolicyWorkspaceCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    target_jurisdiction_id: str = Field(..., min_length=1, max_length=100)
    drafting_template: str = Field(..., min_length=1, max_length=100)
    goal_prompt: str | None = Field(None, max_length=5000)


class PolicyWorkspaceUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    target_jurisdiction_id: str | None = Field(None, min_length=1, max_length=100)
    drafting_template: str | None = Field(None, min_length=1, max_length=100)
    goal_prompt: str | None = Field(None, max_length=5000)
    status: str | None = Field(None, min_length=1, max_length=50)


class PolicyWorkspacePrecedentAdd(BaseModel):
    bill_id: str = Field(..., min_length=1, max_length=200)
    position: int | None = Field(None, ge=0)


class PolicySectionSourceResponse(BaseModel):
    bill_id: str
    identifier: str
    title: str
    jurisdiction_id: str
    note: str | None = None


class PolicySectionResponse(BaseModel):
    id: str
    section_key: str
    heading: str
    purpose: str | None = None
    position: int
    content_markdown: str
    status: str
    provenance: list[PolicySectionSourceResponse] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PolicyWorkspacePrecedentResponse(BaseModel):
    id: int
    bill_id: str
    position: int
    added_at: datetime | None = None
    identifier: str
    title: str
    jurisdiction_id: str
    status: str | None = None


class PolicyWorkspaceResponse(BaseModel):
    id: str
    title: str
    target_jurisdiction_id: str
    drafting_template: str
    goal_prompt: str | None = None
    status: str
    precedent_count: int = 0
    section_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PolicySectionUpdate(BaseModel):
    heading: str | None = Field(None, min_length=1, max_length=200)
    purpose: str | None = Field(None, max_length=5000)


class PolicyOutlineSectionOutput(BaseModel):
    section_key: str = Field(..., min_length=1, max_length=100)
    heading: str = Field(..., min_length=1, max_length=200)
    purpose: str = Field(..., min_length=1, max_length=1000)
    source_bill_ids: list[str] = Field(..., min_length=1, max_length=5)
    source_notes: list[str] = Field(default_factory=list, max_length=5)


class PolicyOutlineOutput(BaseModel):
    sections: list[PolicyOutlineSectionOutput] = Field(default_factory=list, max_length=12)
    drafting_notes: list[str] = Field(default_factory=list, max_length=10)
    confidence: float = Field(ge=0.0, le=1.0)


class PolicyWorkspaceDetailResponse(BaseModel):
    id: str
    title: str
    target_jurisdiction_id: str
    drafting_template: str
    goal_prompt: str | None = None
    status: str
    precedents: list[PolicyWorkspacePrecedentResponse] = Field(default_factory=list)
    sections: list[PolicySectionResponse] = Field(default_factory=list)
    outline_drafting_notes: list[str] = Field(default_factory=list)
    outline_confidence: float | None = None
    outline_generated_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PolicyWorkspaceListResponse(BaseModel):
    data: list[PolicyWorkspaceResponse]
    meta: MetaResponse


# --- Compose action schemas ---

COMPOSE_ACTION_TYPES = frozenset(
    [
        "draft_section",
        "rewrite_selection",
        "tighten_definition",
        "harmonize_with_precedent",
        "analyze_constitutional",
        "analyze_patterns",
    ]
)


class PolicyComposeRequest(BaseModel):
    action_type: str = Field(..., min_length=1, max_length=50)
    instruction_text: str | None = Field(None, max_length=5000)
    selected_text: str | None = Field(None, max_length=10000)


class PolicySectionDraftOutput(BaseModel):
    content_markdown: str = Field(..., min_length=1)
    rationale: str = Field(default="")
    source_bill_ids: list[str] = Field(default_factory=list, max_length=5)
    source_notes: list[str] = Field(default_factory=list, max_length=5)


class PolicyRewriteOutput(BaseModel):
    content_markdown: str = Field(..., min_length=1)
    rationale: str = Field(default="")
    source_bill_ids: list[str] = Field(default_factory=list, max_length=5)
    source_notes: list[str] = Field(default_factory=list, max_length=5)


class PolicyGenerationResponse(BaseModel):
    id: str
    workspace_id: str
    section_id: str | None = None
    action_type: str
    instruction_text: str | None = None
    selected_text: str | None = None
    output_markdown: str
    rationale: str = ""
    provenance: list[PolicySectionSourceResponse] = Field(default_factory=list)
    accepted: bool = False
    created_at: datetime | None = None


class PolicyRevisionResponse(BaseModel):
    id: str
    section_id: str
    generation_id: str | None = None
    change_source: str
    content_markdown: str
    created_at: datetime | None = None


class PolicyHistoryResponse(BaseModel):
    revisions: list[PolicyRevisionResponse] = Field(default_factory=list)
