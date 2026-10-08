"""Visible emergency vehicle evidence; no siren/audio inference."""
from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, Field
from contracts.models import Contract, Direction

class EmergencyTarget(Contract):
    event_id: str = Field(min_length=1, max_length=160)
    direction: Direction
    source_session: UUID
    track_id: int = Field(ge=1)
    kind: Literal['ambulance', 'fire_truck']
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    distance_to_stop: float = Field(ge=0, le=1, allow_inf_nan=False)
    observed_at: AwareDatetime

class EmergencyStatus(Contract):
    state: Literal['idle', 'confirming', 'confirmed', 'servicing', 'recovering', 'unavailable'] = 'idle'
    target: EmergencyTarget | None = None
    candidates: list[EmergencyTarget] = Field(default_factory=list, max_length=32)
    focus: bool = False
    message: str = 'Tidak ada EVP terkonfirmasi.'
    events: list[str] = Field(default_factory=list, max_length=20)
