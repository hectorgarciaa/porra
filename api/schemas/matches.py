from pydantic import BaseModel, Field


class SetMatchResultRequest(BaseModel):
    local_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)
    winner_id: int | None = None
    scorer_ids: list[int] = []
    assists_ids: list[int] = []
    yellow_card_ids: list[int] = []
    red_card_ids: list[int] = []
    has_extra_time: bool = False
    has_penalties: bool = False
    local_penalties: int | None = None
    away_penalties: int | None = None
