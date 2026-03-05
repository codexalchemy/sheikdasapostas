import logging

from fastapi import APIRouter, HTTPException
from app.services.odds_service import odds_service
from app.services.football_service import football_service
from app.models.schemas import MatchData

logger = logging.getLogger(__name__)

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
        logger.exception("Erro ao listar partidas")
        raise HTTPException(status_code=500, detail="Erro ao listar partidas")


@router.get("/events")
async def list_events(competition: str = "BSA"):
    """Lista eventos com odds disponíveis — GRÁTIS, 0 créditos."""
    try:
        events = await odds_service.get_events(competition)
        result = []
        for event in events[:30]:
            result.append(
                {
                    "id": event.get("id", ""),
                    "home_team": event.get("home_team", ""),
                    "away_team": event.get("away_team", ""),
                    "commence_time": event.get("commence_time", ""),
                    "sport_key": event.get("sport_key", ""),
                }
            )
        return {"events": result}
    except Exception as e:
        logger.exception("Erro ao listar eventos")
        raise HTTPException(status_code=500, detail="Erro ao listar eventos")


@router.get("/odds")
async def list_odds(competition: str = "BSA"):
    """Lista odds de partidas disponíveis para uma competição (gasta créditos)."""
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
        logger.exception("Erro ao listar odds")
        raise HTTPException(status_code=500, detail="Erro ao listar odds")


@router.get("/standings/{competition}")
async def get_standings(competition: str):
    """Classificação de uma competição."""
    try:
        table = await football_service.get_standings(competition)
        return {"standings": table}
    except Exception as e:
        logger.exception("Erro ao buscar classificação")
        raise HTTPException(status_code=500, detail="Erro ao buscar classificação")


@router.get("/quota")
async def get_quota():
    """Verifica créditos restantes da Odds API (grátis, info dos headers)."""
    try:
        sports = await odds_service.get_sports()
        return {
            "total_sports": len(sports),
            "cache_ttl_seconds": 1800,
            "tip": "Use /events (grátis) para listar jogos. /odds gasta 2 créditos por liga."
        }
    except Exception as e:
        logger.exception("Erro ao verificar quota")
        raise HTTPException(status_code=500, detail="Erro ao verificar quota")
