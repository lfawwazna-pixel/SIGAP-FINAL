"""Map poses shared by synthetic traffic and calibrated video projections."""
from typing import Literal
from pydantic import Field
from contracts.models import Contract, Direction


class VehicleView(Contract):
    id: int = Field(ge=1)
    origin: Direction
    movement: Literal['left', 'straight', 'right']
    kind: Literal['car', 'motorcycle', 'bus', 'truck', 'ambulance', 'fire_engine']
    x: float = Field(ge=-420, le=1220, allow_inf_nan=False)
    y: float = Field(ge=-420, le=1220, allow_inf_nan=False)
    heading: float = Field(ge=-180, le=180, allow_inf_nan=False)
    stopped: bool
    served: bool
    distance_to_stop: float = Field(ge=0, allow_inf_nan=False)
    lane: Literal['outer', 'middle', 'inner']
    target_lane: Literal['outer', 'middle', 'inner']
    changing_to: Literal['outer', 'middle', 'inner'] | None
    stop_reason: Literal['following', 'yielding', 'signal', 'exit_blocked', 'conflict', 'safety_gap', 'stationary'] | None = None
