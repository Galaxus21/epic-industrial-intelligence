"""
EPIC — The shape of a work-order change an AI proposes, and which parts of it the signed-in user may apply.

A proposal comes from a model, and a saved step list comes from a model through the browser, so both are validated
like any client payload: known fields only, bounded sizes, a risk level from a fixed set, and a step index that names
an existing step. A proposal is then cut to what the user's role may apply, using the same role groups as the routes
that apply each part (work_orders.py): FIELD_ROLES tick and add steps, APPROVER_ROLES change the description and risk
level. "Apply changes" therefore never stops halfway on a role refusal, and the model is told the role up front.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field, ValidationError, model_validator

from app.core.roles import APPROVER_ROLES, FIELD_ROLES

logger = logging.getLogger(__name__)

MAX_TITLE_CHARS = 200
MAX_TEXT_CHARS = 4000
MAX_NOTE_CHARS = 1000
MAX_LABEL_CHARS = 40
MAX_STEP_MINUTES = 24 * 60
MAX_STEPS = 50
DEFAULT_PHASE = "Execution"
DETAIL_FIELDS = ("description", "risk_level")
STEP_FIELDS = ("toggle_steps", "add_steps")
PERMISSIONS = (
    (DETAIL_FIELDS, APPROVER_ROLES, "change the description and risk level"),
    (STEP_FIELDS, FIELD_ROLES, "tick and add steps"),
)


def _titleCased(value: Any) -> Any:
    return value.strip().title() if isinstance(value, str) else value


RiskLevel = Annotated[Literal["Critical", "High", "Medium", "Low"], BeforeValidator(_titleCased)]


class ProposedStep(BaseModel):
    """One work-order step as a client or a model may submit it; unknown keys are dropped."""

    step: int | None = Field(None, ge=1, le=MAX_STEPS)
    phase: str = Field(DEFAULT_PHASE, max_length=MAX_LABEL_CHARS)
    title: str = Field("", max_length=MAX_TITLE_CHARS)
    description: str = Field("", max_length=MAX_TEXT_CHARS)
    safety_note: str | None = Field(None, max_length=MAX_NOTE_CHARS)
    expected_duration_minutes: int | None = Field(None, ge=0, le=MAX_STEP_MINUTES)

    @model_validator(mode="after")
    def _saysWhatToDo(self) -> "ProposedStep":
        # A model may leave out the title, but a step with neither a title nor a description instructs nobody.
        if not (self.title.strip() or self.description.strip()):
            raise ValueError("a step needs a title or a description")
        return self


class StepToggle(BaseModel):
    step_index: int = Field(ge=0)
    checked: bool


class ProposedChanges(BaseModel):
    description: str | None = Field(None, min_length=1, max_length=MAX_TEXT_CHARS)
    risk_level: RiskLevel | None = None
    toggle_steps: list[StepToggle] = Field(default_factory=list, max_length=MAX_STEPS)
    add_steps: list[ProposedStep] = Field(default_factory=list, max_length=MAX_STEPS)


def permittedProposal(raw: Any, role: str, stepCount: int) -> tuple[dict[str, Any] | None, list[str]]:
    """The model's proposal validated and cut to what `role` may apply: (changes or None, names of withheld fields)."""
    if not raw:
        return None, []
    try:
        proposal = ProposedChanges.model_validate(raw).model_dump(exclude_none=True)
    except ValidationError as exc:
        logger.warning("Discarding an invalid AI work-order proposal: %s", exc)
        return None, []
    proposal["toggle_steps"] = [toggle for toggle in proposal["toggle_steps"] if toggle["step_index"] < stepCount]
    withheld: list[str] = []
    for fields, roles, _ in PERMISSIONS:
        if role not in roles:
            withheld += [field for field in fields if proposal.pop(field, None)]
    proposal = {field: value for field, value in proposal.items() if value}
    return proposal or None, withheld


def roleNote(role: str) -> str:
    """What the model is told about the user, so it proposes only changes the user can apply."""
    allowed = [ability for _, roles, ability in PERMISSIONS if role in roles]
    abilities = " and ".join(allowed) if allowed else "only ask questions"
    return f"The user is a {role}. They can {abilities}; do not propose changes they cannot apply."
