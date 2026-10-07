from typing import Literal
from pydantic import AwareDatetime, Field
from contracts.models import Contract, TrafficEvent

class EventArchivePage(Contract):
    intersection_id: str
    events: list[TrafficEvent]
    next_before: int | None = Field(ge=1)
    has_more: bool
    generated_at: AwareDatetime
    filter: Literal['all', 'phase', 'incident']
