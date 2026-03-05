from fastapi import APIRouter, HTTPException
from app.services.odds_service import odds_service
from app.services.football_service import football_service
from app.models.schemas import MatchData

router = APIRouter(prefix="/api/matches", tags=["matches"])


@router.get("/")
async def list_matches(competition: str = "BSA"):
    """Lista partidas agendadas de uma competição."""
    try:
        matches = await football_service.get_matches(competition)
        result = []
        for m in matches[:20]:
            result.append(
                {
                    "id": m.get("id"),
                    "date": m.get("utcDate", ""),
                    "status": m.get("status", ""),
                    "home_team": m.get("homeTeam", {}).get("name", ""),
                    "away_team": m.get("awayTeam", {}).get("name", ""),
                    "competition": m.get("competition", {}).get("name", ""),
                }
            )
        return {"matches": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/odds")
async def list_odds(competition: str = "BSA"):
    """Lista odds de partidas disponíveis para uma competição."""
    try:
        events = await odds_service.get_odds(competition)
        result = []
        for event in events[:20]:
            odds = odds_service.parse_odds(event)
            result.append(
                {
                    "id": event.get("id", ""),
                    "home_team": event.get("home_team", ""),
                    "away_team": event.get("away_team", ""),
                    "commence_time": event.get("commence_time", ""),
                    "odds": [o.model_dump() for o in odds],
                }
            )
        return {"events": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/standings/{competition}")
async def get_standings(competition: str):
    """Classificação de uma competição."""
    try:
        table = await football_service.get_standings(competition)
        return {"standings": table}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
