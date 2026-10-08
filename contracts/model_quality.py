"""Evaluation evidence; absence never becomes an invented score."""
from pydantic import Field
from contracts.models import Contract

class ClassMetrics(Contract):
    precision: float = Field(ge=0,le=1,allow_inf_nan=False)
    recall: float = Field(ge=0,le=1,allow_inf_nan=False)
    map50: float = Field(ge=0,le=1,allow_inf_nan=False)
    map5095: float = Field(ge=0,le=1,allow_inf_nan=False)

class EvaluationSplit(Contract):
    per_class: dict[str,ClassMetrics]

class ModelQuality(Contract):
    available: bool
    model_label: str
    model_sha256: str | None = None
    reports: dict[str,EvaluationSplit] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    message: str
