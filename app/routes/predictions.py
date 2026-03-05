import asyncio
import logging

from fastapi import APIRouter, HTTPException
from app.services.odds_service import odds_service
from app.services.football_service import football_service
from app.services.stats_engine import stats_engine
from app.services.ai_analyzer import ai_analyzer
from app.models.schemas import MatchData, Prediction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


@router.get("/")
async def get_predictions(competition: str = "BSA"):
    """
    Gera previsões completas para partidas agendadas.
    Combina: dados de classificação + odds + modelo Poisson + análise IA.
    """
    try:
        # 1. Buscar partidas e odds em paralelo
        matches_task = football_service.get_matches(competition)
        odds_task = odds_service.get_odds(competition)
        matches, odds_events = await asyncio.gather(matches_task, odds_task)

        predictions = []

        for m in matches[:20]:
            home = m.get("homeTeam", {}).get("name", "")
            away = m.get("awayTeam", {}).get("name", "")

            # 2. Buscar stats dos times em paralelo
            home_stats, away_stats = await asyncio.gather(
                football_service.get_team_stats(home, competition),
                football_service.get_team_stats(away, competition),
            )

            # 3. Encontrar odds correspondentes
            match_odds = []
            for event in odds_events:
                if (
                    _fuzzy_match(event.get("home_team", ""), home)
                    and _fuzzy_match(event.get("away_team", ""), away)
                ):
                    match_odds = odds_service.parse_odds(event)
                    break

            # 4. Montar MatchData
            match_data = MatchData(
                match_id=str(m.get("id", "")),
                competition=m.get("competition", {}).get("name", competition),
                home_team=home,
                away_team=away,
                date=m.get("utcDate", ""),
                status=m.get("status", ""),
                odds=match_odds,
                home_stats=home_stats,
                away_stats=away_stats,
            )

            # 5. Modelo Poisson
            poisson_pred = None
            if home_stats and away_stats:
                poisson_pred = stats_engine.poisson_prediction(home_stats, away_stats)

            # 6. Value Bets
            value_bets = []
            if poisson_pred and match_odds:
                real_probs = {
                    "home_win": poisson_pred.home_win_prob,
                    "draw": poisson_pred.draw_prob,
                    "away_win": poisson_pred.away_win_prob,
                }
                value_bets = odds_service.find_value_bets(match_odds, real_probs)

            # 7. Análise IA
            ai_result = await ai_analyzer.analyze_match(
                match_data, poisson_pred, value_bets
            )

            prediction = Prediction(
                match=match_data,
                poisson=poisson_pred,
                value_bets=value_bets,
                ai_analysis=ai_result.get("analysis", ""),
                confidence=ai_result.get("confidence", 0),
                recommended_bet=ai_result.get("recommended_bet", ""),
                recommended_market=ai_result.get("recommended_market", ""),
            )
            predictions.append(prediction)

        return {
            "predictions": [p.model_dump() for p in predictions],
            "total": len(predictions),
        }

    except Exception as e:
        logger.exception("Erro ao gerar previsões")
        raise HTTPException(status_code=500, detail="Erro ao gerar previsões")


@router.get("/quick/{home_team}/{away_team}")
async def quick_prediction(home_team: str, away_team: str, competition: str = "BSA"):
    """Previsão rápida para uma partida específica informando os times."""
    try:
        home_stats, away_stats = await asyncio.gather(
            football_service.get_team_stats(home_team, competition),
            football_service.get_team_stats(away_team, competition),
        )

        match_data = MatchData(
            match_id="quick",
            competition=competition,
            home_team=home_team,
            away_team=away_team,
            date="",
            status="PREVIEW",
            home_stats=home_stats,
            away_stats=away_stats,
        )

        poisson_pred = None
        if home_stats and away_stats:
            poisson_pred = stats_engine.poisson_prediction(home_stats, away_stats)

        ai_result = await ai_analyzer.analyze_match(match_data, poisson_pred, [])

        return {
            "match": match_data.model_dump(),
            "poisson": poisson_pred.model_dump() if poisson_pred else None,
            "analysis": ai_result,
        }

    except Exception as e:
        logger.exception("Erro na previsão rápida")
        raise HTTPException(status_code=500, detail="Erro ao gerar previsão")


def _fuzzy_match(name1: str, name2: str) -> bool:
    """Verifica se dois nomes de times são compatíveis (word-level matching)."""
    n1 = name1.lower().strip()
    n2 = name2.lower().strip()
    if n1 == n2:
        return True
    # Tokeniza e compara palavras significativas (ignora palavras curtas como FC, SC, CF)
    stop = {"fc", "sc", "cf", "ac", "de", "da", "do", "the", "club", "1."}
    words1 = {w for w in n1.split() if w not in stop and len(w) > 2}
    words2 = {w for w in n2.split() if w not in stop and len(w) > 2}
    if not words1 or not words2:
        return n1 in n2 or n2 in n1
    common = words1 & words2
    return len(common) >= 1 and len(common) >= min(len(words1), len(words2)) * 0.5
