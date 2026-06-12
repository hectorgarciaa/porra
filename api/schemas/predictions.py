from pydantic import BaseModel, Field


class UpsertMatchPredictionRequest(BaseModel):
    local_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)
    winner_team_id: int | None = None
    has_extra_time: bool = False
    has_penalties: bool = False


class UpsertGlobalPredictionRequest(BaseModel):
    winner_team_id: int | None = None
    runner_up_team_id: int | None = None
    third_place_team_id: int | None = None
    fourth_place_team_id: int | None = None
    best_player_player_id: int | None = None
    best_gk_player_id: int | None = None
    best_young_player_id: int | None = None
    max_scorer_player_id: int | None = None
    max_assister_player_id: int | None = None
    max_yellow_cards_player_id: int | None = None
    max_red_cards_player_id: int | None = None
    revelation_team_id: int | None = None
    disappointment_team_id: int | None = None
    revelation_player_id: int | None = None
    disappointment_player_id: int | None = None
