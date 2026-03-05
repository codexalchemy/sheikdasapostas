from pydantic import BaseModel
from typing import Optional


class TeamStats(BaseModel):
    name: str
    played: int = 0
    won: int = 0
    draw: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0
    position: int = 0
    avg_goals_scored: float = 0.0
    avg_goals_conceded: float = 0.0


class MatchOdds(BaseModel):
    bookmaker: str
    home_win: float
    draw: float
    away_win: float
    over_25: Optional[float] = None
    under_25: Optional[float] = None


class MatchData(BaseModel):
    match_id: str
    competition: str
    home_team: str
    away_team: str
    date: str
    status: str
    odds: list[MatchOdds] = []
    home_stats: Optional[TeamStats] = None
    away_stats: Optional[TeamStats] = None


class PoissonPrediction(BaseModel):
    home_goals_expected: float
    away_goals_expected: float
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    over_25_prob: float
    under_25_prob: float
    btts_prob: float
    score_probabilities: dict[str, float] = {}


class Prediction(BaseModel):
    match: MatchData
    poisson: Optional[PoissonPrediction] = None
    value_bets: list[dict] = []
    ai_analysis: str = ""
    confidence: float = 0.0
    recommended_bet: str = ""
    recommended_market: str = ""
    home_form: list[str] = []
    away_form: list[str] = []
