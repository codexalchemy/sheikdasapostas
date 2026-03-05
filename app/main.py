import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models.database import init_db
from app.routes import admin, matches, predictions

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Sheik das Apostas — inicializando...")
    await init_db()
    STATIC_DIR.mkdir(exist_ok=True)
    logger.info("✅ Banco de dados pronto")

    apis_ok = []
    if settings.ODDS_API_KEY:
        apis_ok.append("The Odds API")
    if settings.FOOTBALL_DATA_API_KEY:
        apis_ok.append("Football-Data.org")
    if settings.OPENAI_API_KEY:
        apis_ok.append("OpenAI")
    if settings.TELEGRAM_BOT_TOKEN:
        apis_ok.append("Telegram Bot")

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
    version="2.0.0",
    lifespan=lifespan,
)

# Rotas da API
app.include_router(matches.router)
app.include_router(predictions.router)
app.include_router(admin.router)

# Arquivos estáticos (PWA, ícones, etc.)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Erro não tratado")
    return JSONResponse(status_code=500, content={"detail": "Erro interno do servidor"})


@app.get("/", response_class=HTMLResponse)
async def index():
    """Dashboard principal."""
    html_path = TEMPLATES_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/manifest.json")
async def pwa_manifest():
    """PWA Manifest."""
    import json
    manifest_path = STATIC_DIR / "manifest.json"
    if manifest_path.exists():
        return JSONResponse(
            content=json.loads(manifest_path.read_text(encoding="utf-8")),
            media_type="application/manifest+json",
        )
    return JSONResponse(content={
        "name": "Sheik das Apostas",
        "short_name": "Sheik",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0b0e14",
        "theme_color": "#c9a84c",
    })


@app.get("/sw.js")
async def service_worker():
    """Service Worker para PWA."""
    sw_path = STATIC_DIR / "sw.js"
    if sw_path.exists():
        return Response(
            content=sw_path.read_text(encoding="utf-8"),
            media_type="application/javascript",
        )
    return Response(content="// SW placeholder", media_type="application/javascript")


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
        "version": "2.0.0",
        "features": [
            "poisson", "elo", "form_guide", "h2h", "accumulator",
            "track_record", "live_scores", "notifications", "pwa",
            "theme_toggle", "telegram", "aposta_do_dia", "charts",
        ],
        "apis": {
            "odds_api": settings.ODDS_API_KEY not in placeholders,
            "football_data": settings.FOOTBALL_DATA_API_KEY not in placeholders,
            "openai": settings.OPENAI_API_KEY not in placeholders,
            "telegram": bool(settings.TELEGRAM_BOT_TOKEN),
        },
    }
