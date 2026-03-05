import asyncio
import logging
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from app.services.odds_service import odds_service
from app.services.football_service import football_service
from app.services.stats_engine import stats_engine
from app.services.ai_analyzer import ai_analyzer
from app.models.schemas import MatchData, Prediction
from app.models.database import get_db
from app.services.telegram_service import telegram_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


@router.get("/")
async def get_predictions(competition: str = "BSA"):
    """
    Gera previsões completas para partidas agendadas.
    Combina: dados de classificação + odds + modelo Poisson + análise IA.
    """
    try:
        # 1. Buscar partidas, odds e resultados recentes em paralelo
        matches_task = football_service.get_matches(competition)
        odds_task = odds_service.get_odds(competition)
        recent_task = football_service.get_recent_results(competition)
        matches, odds_events, recent_matches = await asyncio.gather(
            matches_task, odds_task, recent_task
        )

        predictions = []

        for m in matches[:20]:
            home = m.get("homeTeam", {}).get("name", "")
            away = m.get("awayTeam", {}).get("name", "")
            match_id = str(m.get("id", ""))

            # 2. Buscar stats dos times em paralelo
            home_stats, away_stats = await asyncio.gather(
                football_service.get_team_stats(home, competition),
                football_service.get_team_stats(away, competition),
            )

            # 3. Form guide
            home_form = football_service.get_team_form(home, recent_matches)
            away_form = football_service.get_team_form(away, recent_matches)

            # 4. Encontrar odds correspondentes
            match_odds = []
            for event in odds_events:
                if (
                    _fuzzy_match(event.get("home_team", ""), home)
                    and _fuzzy_match(event.get("away_team", ""), away)
                ):
                    match_odds = odds_service.parse_odds(event)
                    break

            # 5. Montar MatchData
            match_data = MatchData(
                match_id=match_id,
                competition=m.get("competition", {}).get("name", competition),
                home_team=home,
                away_team=away,
                date=m.get("utcDate", ""),
                status=m.get("status", ""),
                odds=match_odds,
                home_stats=home_stats,
                away_stats=away_stats,
            )

            # 6. Modelo Poisson
            poisson_pred = None
            if home_stats and away_stats:
                poisson_pred = stats_engine.poisson_prediction(home_stats, away_stats)

            # 7. Value Bets
            value_bets = []
            if poisson_pred and match_odds:
                real_probs = {
                    "home_win": poisson_pred.home_win_prob,
                    "draw": poisson_pred.draw_prob,
                    "away_win": poisson_pred.away_win_prob,
                }
                value_bets = odds_service.find_value_bets(match_odds, real_probs)

            # 8. Análise IA
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
                home_form=home_form,
                away_form=away_form,
            )
            predictions.append(prediction)

            # 9. Salvar previsão no histórico
            try:
                db = await get_db()
                await db.execute(
                    """INSERT OR REPLACE INTO predictions_history
                       (match_id, prediction_type, predicted_outcome, confidence, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (match_id, ai_result.get("recommended_market", "1x2"),
                     ai_result.get("recommended_bet", ""),
                     ai_result.get("confidence", 0),
                     datetime.now(timezone.utc).isoformat()),
                )
                await db.commit()
                await db.close()
            except Exception:
                pass

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


@router.get("/best")
async def best_prediction(competition: str = "BSA"):
    """Retorna a melhor previsão do dia (Aposta do Dia)."""
    try:
        matches_task = football_service.get_matches(competition)
        odds_task = odds_service.get_odds(competition)
        recent_task = football_service.get_recent_results(competition)
        matches, odds_events, recent = await asyncio.gather(
            matches_task, odds_task, recent_task
        )

        best = None
        best_confidence = 0

        for m in matches[:20]:
            home = m.get("homeTeam", {}).get("name", "")
            away = m.get("awayTeam", {}).get("name", "")
            home_stats, away_stats = await asyncio.gather(
                football_service.get_team_stats(home, competition),
                football_service.get_team_stats(away, competition),
            )
            match_odds = []
            for event in odds_events:
                if _fuzzy_match(event.get("home_team", ""), home) and _fuzzy_match(event.get("away_team", ""), away):
                    match_odds = odds_service.parse_odds(event)
                    break
            match_data = MatchData(
                match_id=str(m.get("id", "")), competition=m.get("competition", {}).get("name", competition),
                home_team=home, away_team=away, date=m.get("utcDate", ""),
                status=m.get("status", ""), odds=match_odds,
                home_stats=home_stats, away_stats=away_stats,
            )
            poisson_pred = None
            if home_stats and away_stats:
                poisson_pred = stats_engine.poisson_prediction(home_stats, away_stats)
            value_bets = []
            if poisson_pred and match_odds:
                real_probs = {"home_win": poisson_pred.home_win_prob, "draw": poisson_pred.draw_prob, "away_win": poisson_pred.away_win_prob}
                value_bets = odds_service.find_value_bets(match_odds, real_probs)
            ai_result = await ai_analyzer.analyze_match(match_data, poisson_pred, value_bets)
            conf = ai_result.get("confidence", 0)
            if conf > best_confidence:
                best_confidence = conf
                home_form = football_service.get_team_form(home, recent)
                away_form = football_service.get_team_form(away, recent)
                best = Prediction(
                    match=match_data, poisson=poisson_pred, value_bets=value_bets,
                    ai_analysis=ai_result.get("analysis", ""), confidence=conf,
                    recommended_bet=ai_result.get("recommended_bet", ""),
                    recommended_market=ai_result.get("recommended_market", ""),
                    home_form=home_form, away_form=away_form,
                )

        if best:
            return {"best": best.model_dump()}
        return {"best": None}
    except Exception as e:
        logger.exception("Erro ao buscar melhor previsão")
        raise HTTPException(status_code=500, detail="Erro ao buscar aposta do dia")


@router.get("/h2h/{match_id}")
async def get_h2h(match_id: int):
    """Retorna dados de confrontos diretos."""
    try:
        h2h = await football_service.get_head2head(match_id)
        return {"h2h": h2h}
    except Exception as e:
        logger.exception("Erro ao buscar H2H")
        raise HTTPException(status_code=500, detail="Erro ao buscar head-to-head")


@router.get("/track-record")
async def track_record():
    """Retorna estatísticas do track record de previsões."""
    try:
        db = await get_db()
        cursor = await db.execute(
            """SELECT COUNT(*) as total,
                      SUM(CASE WHEN correct = 1 THEN 1 ELSE 0 END) as hits,
                      SUM(CASE WHEN correct = 0 THEN 1 ELSE 0 END) as misses,
                      SUM(CASE WHEN correct IS NULL THEN 1 ELSE 0 END) as pending,
                      AVG(confidence) as avg_confidence
               FROM predictions_history"""
        )
        row = await cursor.fetchone()
        total = row[0] or 0
        hits = row[1] or 0
        misses = row[2] or 0
        pending = row[3] or 0
        avg_conf = round(row[4] or 0, 1)
        accuracy = round((hits / (hits + misses)) * 100, 1) if (hits + misses) > 0 else 0

        # Últimas 20 previsões
        cursor2 = await db.execute(
            """SELECT match_id, prediction_type, predicted_outcome, confidence,
                      actual_outcome, correct, created_at
               FROM predictions_history ORDER BY created_at DESC LIMIT 20"""
        )
        recent = []
        for r in await cursor2.fetchall():
            recent.append({
                "match_id": r[0], "type": r[1], "predicted": r[2],
                "confidence": r[3], "actual": r[4],
                "correct": r[5], "date": r[6],
            })
        await db.close()
        return {
            "total": total, "hits": hits, "misses": misses, "pending": pending,
            "accuracy": accuracy, "avg_confidence": avg_conf, "recent": recent,
        }
    except Exception as e:
        logger.exception("Erro ao buscar track record")
        return {"total": 0, "hits": 0, "misses": 0, "pending": 0, "accuracy": 0, "avg_confidence": 0, "recent": []}


@router.post("/accumulator")
async def calculate_accumulator(selections: list[dict]):
    """Calcula odds combinadas para uma acumuladinha."""
    if not selections or len(selections) < 2:
        raise HTTPException(status_code=400, detail="Mínimo 2 seleções")
    if len(selections) > 15:
        raise HTTPException(status_code=400, detail="Máximo 15 seleções")

    combined_odd = 1.0
    combined_prob = 1.0
    for s in selections:
        odd = s.get("odd", 1.0)
        prob = s.get("prob", 0.5)
        combined_odd *= odd
        combined_prob *= prob

    return {
        "selections_count": len(selections),
        "combined_odd": round(combined_odd, 2),
        "combined_prob": round(combined_prob * 100, 2),
        "potential_return_per_unit": round(combined_odd, 2),
    }


@router.get("/elo-rankings")
async def elo_rankings():
    """Retorna rankings ELO dos times."""
    try:
        db = await get_db()
        cursor = await db.execute(
            "SELECT team_name, elo_rating, matches_played, last_updated FROM team_elo ORDER BY elo_rating DESC LIMIT 50"
        )
        rankings = []
        for r in await cursor.fetchall():
            rankings.append({"team": r[0], "elo": round(r[1], 1), "matches": r[2], "updated": r[3]})
        await db.close()
        return {"rankings": rankings}
    except Exception as e:
        logger.exception("Erro ao buscar ELO rankings")
        return {"rankings": []}


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


@router.post("/telegram/send-daily")
async def send_telegram_daily(competition: str = "BSA"):
    """Envia resumo diário das previsões via Telegram."""
    if not telegram_service.configured:
        raise HTTPException(status_code=400, detail="Telegram não configurado")
    try:
        resp = await get_predictions(competition)
        preds = resp.get("predictions", [])
        if not preds:
            return {"sent": False, "reason": "Sem previsões"}
        msg = telegram_service.format_daily_summary(preds)
        sent = await telegram_service.send_message(msg)
        return {"sent": sent}
    except Exception as e:
        logger.exception("Erro ao enviar Telegram")
        raise HTTPException(status_code=500, detail="Erro ao enviar via Telegram")
