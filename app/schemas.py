from typing import Literal
from pydantic import BaseModel, Field, field_validator

DatasetType = Literal["计划任务书", "立项申请书"]

class RuleHit(BaseModel):
    rule_id: str
    rule_name: str
    evidence: str
    polarity: Literal["支持", "反对"] = "支持"
    confidence: float = Field(ge=0, le=1)

class Judgment(BaseModel):
    id: str
    dataset_type: DatasetType
    intent: str
    label: Literal["通过", "不通过"]
    matched_rules: list[RuleHit]
    reason: str
    confidence: float = Field(ge=0, le=1)
    needs_review: bool = False

class EvidencePack(BaseModel):
    facts: list[str]
    missing: list[str]
    contradictions: list[str]

    @field_validator("facts", "missing", "contradictions", mode="before")
    @classmethod
    def normalize_text_lists(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value

class RuleCandidate(BaseModel):
    rule_id: str
    rule_name: str
    criterion: str
    required_evidence: list[str]
    blocking: bool = False

    @field_validator("required_evidence", mode="before")
    @classmethod
    def normalize_required_evidence(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value
