import logging
import os
import platform
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.config import settings
from app.models.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# ── Ring buffer para logs in-memory ──────────────────────────────────
MAX_LOG_LINES = 500
log_buffer: deque[dict] = deque(maxlen=MAX_LOG_LINES)


class BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        log_buffer.append({
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc)
                         .strftime("%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": self.format(record),
        })


_handler = BufferHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger().addHandler(_handler)

PLACEHOLDER_KEYS = {
    "cole_sua_chave_the_odds_api_aqui",
    "cole_sua_chave_football_data_aqui",
    "cole_sua_chave_openai_aqui",
    "",
}


def _api_status(key: str) -> dict:
    active = key not in PLACEHOLDER_KEYS
    return {"active": active, "key_preview": f"{key[:8]}..." if active else "não configurada"}


@router.get("/", response_class=HTMLResponse)
async def admin_dashboard():
    html_path = TEMPLATES_DIR / "admin.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@router.get("/api/status")
async def system_status():
    """Status geral do sistema, APIs e ambiente."""
    uptime_file = Path("/proc/uptime")
    uptime = None
    if uptime_file.exists():
        uptime = float(uptime_file.read_text().split()[0])

    return {
        "system": {
            "python": sys.version,
            "platform": platform.platform(),
            "pid": os.getpid(),
            "uptime_seconds": uptime,
        },
        "apis": {
            "the_odds_api": {
                **_api_status(settings.ODDS_API_KEY),
                "base_url": settings.ODDS_API_BASE_URL,
                "description": "Odds em tempo real de 40+ casas de apostas",
                "docs": "https://the-odds-api.com/liveapi/guides/v4/",
                "free_tier": "500 requests/mês",
            },
            "football_data": {
                **_api_status(settings.FOOTBALL_DATA_API_KEY),
                "base_url": settings.FOOTBALL_API_BASE_URL,
                "description": "Classificações, resultados e dados de competições",
                "docs": "https://www.football-data.org/documentation/quickstart",
                "free_tier": "10 requests/minuto",
            },
            "openai": {
                **_api_status(settings.OPENAI_API_KEY),
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
                "description": "Análise de partidas com IA generativa",
                "docs": "https://platform.openai.com/docs",
                "free_tier": "Pay-as-you-go",
            },
        },
        "config": {
            "database": settings.DATABASE_PATH,
            "log_level": settings.LOG_LEVEL,
            "supported_leagues": settings.SUPPORTED_LEAGUES,
        },
    }


@router.get("/api/algorithm")
async def algorithm_info():
    """Detalhes completos do algoritmo e pipeline de previsão."""
    return {
        "pipeline": [
            {
                "step": 1,
                "name": "Coleta de Partidas",
                "source": "Football-Data.org API",
                "endpoint": "/v4/competitions/{code}/matches?status=SCHEDULED",
                "description": "Busca partidas agendadas da competição selecionada. Em caso de falha, usa dados de exemplo.",
            },
            {
                "step": 2,
                "name": "Coleta de Odds",
                "source": "The Odds API",
                "endpoint": "/v4/sports/soccer/odds",
                "description": "Obtém odds de múltiplas casas (Bet365, Betano, etc.) nos mercados h2h e totals, formato decimal.",
            },
            {
                "step": 3,
                "name": "Estatísticas dos Times",
                "source": "Football-Data.org API",
                "endpoint": "/v4/competitions/{code}/standings",
                "description": "Classificação com jogos, vitórias, empates, derrotas, gols pró/contra. Calcula médias ofensivas e defensivas.",
            },
            {
                "step": 4,
                "name": "Modelo Poisson",
                "source": "Motor Estatístico Interno",
                "description": "Calcula probabilidades de cada placar usando distribuição de Poisson.",
                "parameters": {
                    "league_avg_goals": 2.7,
                    "home_advantage_factor": 1.15,
                    "max_goals_matrix": 7,
                    "top_scores_returned": 10,
                },
                "formula": {
                    "home_attack": "avg_goals_scored_home / league_avg_per_team",
                    "away_defense": "avg_goals_conceded_away / league_avg_per_team",
                    "home_expected_goals": "home_attack × away_defense × league_avg_per_team × 1.15",
                    "away_expected_goals": "away_attack × home_defense × league_avg_per_team / 1.15",
                    "probability": "P(home=i) × P(away=j) = poisson.pmf(i, λ_home) × poisson.pmf(j, λ_away)",
                },
                "outputs": [
                    "home_win_prob", "draw_prob", "away_win_prob",
                    "over_25_prob", "under_25_prob", "btts_prob",
                    "score_probabilities (top 10 placares)",
                ],
            },
            {
                "step": 5,
                "name": "Detecção de Value Bets",
                "source": "Motor Estatístico Interno",
                "description": "Compara probabilidade real (Poisson) com probabilidade implícita das odds. Se real > implícita, é value bet.",
                "formula": {
                    "implied_prob": "1 / odd",
                    "edge": "real_prob - implied_prob",
                    "is_value": "edge > 0",
                },
            },
            {
                "step": 6,
                "name": "Análise com IA",
                "source": "OpenAI GPT-4o-mini",
                "description": "Envia todos os dados (stats, odds, Poisson, value bets) para a IA gerar análise em linguagem natural.",
                "fallback": "Análise local baseada nos dados numéricos quando OpenAI não está configurada.",
                "system_prompt": "Analista esportivo especialista. Responde em PT-BR com: ANÁLISE, CONFIANÇA (0-100), APOSTA RECOMENDADA, MERCADO.",
            },
        ],
        "elo_system": {
            "description": "Sistema ELO adaptado para futebol",
            "initial_rating": 1500,
            "k_factor": 32,
            "home_advantage": 65,
            "margin_factor": {
                "1_goal": 1.0,
                "2_goals": 1.5,
                "3+_goals": "(11 + diff) / 8",
            },
        },
        "data_flow": {
            "input": ["Football-Data.org (partidas + classificação)", "The Odds API (odds multibookmaker)"],
            "processing": ["Poisson Model (probabilidades)", "Value Bet Detector (edge calculation)", "ELO System (team strength)"],
            "output": ["AI Analysis (GPT-4o-mini)", "Predictions JSON", "Dashboard Rendering"],
        },
    }


@router.get("/api/logs")
async def get_logs(level: str = "ALL", limit: int = 200):
    """Retorna logs do sistema."""
    logs = list(log_buffer)
    if level != "ALL":
        logs = [l for l in logs if l["level"] == level.upper()]
    return {"logs": logs[-limit:], "total": len(logs)}


@router.get("/api/db/stats")
async def db_stats():
    """Estatísticas do banco de dados."""
    db = await get_db()
    try:
        tables = {}
        for table in ["cached_matches", "cached_odds", "predictions_history", "team_elo"]:
            cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
            row = await cursor.fetchone()
            tables[table] = row[0]

        recent_predictions = []
        cursor = await db.execute(
            "SELECT * FROM predictions_history ORDER BY created_at DESC LIMIT 20"
        )
        rows = await cursor.fetchall()
        for r in rows:
            recent_predictions.append({
                "id": r[0], "match_id": r[1], "type": r[2],
                "predicted": r[3], "confidence": r[4],
                "actual": r[5], "correct": r[6], "created_at": r[7],
            })

        elo_ratings = []
        cursor = await db.execute("SELECT * FROM team_elo ORDER BY elo_rating DESC")
        rows = await cursor.fetchall()
        for r in rows:
            elo_ratings.append({"team": r[0], "elo": r[1], "updated": r[2]})

        db_path = settings.DATABASE_PATH
        db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

        return {
            "tables": tables,
            "db_size_kb": round(db_size / 1024, 1),
            "recent_predictions": recent_predictions,
            "elo_ratings": elo_ratings,
        }
    finally:
        await db.close()
