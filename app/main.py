import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models.database import init_db
from app.routes import matches, predictions

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Sheik das Apostas — inicializando...")
    await init_db()
    logger.info("✅ Banco de dados pronto")

    apis_ok = []
    if settings.ODDS_API_KEY:
        apis_ok.append("The Odds API")
    if settings.FOOTBALL_DATA_API_KEY:
        apis_ok.append("Football-Data.org")
    if settings.OPENAI_API_KEY:
        apis_ok.append("OpenAI")

    if apis_ok:
        logger.info(f"🔑 APIs configuradas: {', '.join(apis_ok)}")
    else:
        logger.warning(
            "⚠️  Nenhuma API key configurada — usando dados de exemplo. "
            "Copie .env.example para .env e preencha suas chaves."
        )

    yield
    logger.info("Sheik das Apostas — encerrando")


app = FastAPI(
    title="Sheik das Apostas",
    description="Plataforma inteligente de análise esportiva com IA",
    version="1.0.0",
    lifespan=lifespan,
)

# Rotas da API
app.include_router(matches.router)
app.include_router(predictions.router)


@app.get("/", response_class=HTMLResponse)
async def index():
    """Dashboard principal."""
    html_path = TEMPLATES_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/health")
async def health():
    placeholders = {
        "cole_sua_chave_the_odds_api_aqui",
        "cole_sua_chave_football_data_aqui",
        "cole_sua_chave_openai_aqui",
        "",
    }
    return {
        "status": "ok",
        "apis": {
            "odds_api": settings.ODDS_API_KEY not in placeholders,
            "football_data": settings.FOOTBALL_DATA_API_KEY not in placeholders,
            "openai": settings.OPENAI_API_KEY not in placeholders,
        },
    }
