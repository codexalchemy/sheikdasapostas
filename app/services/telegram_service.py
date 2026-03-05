import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class TelegramService:
    """Serviço leve de integração com Telegram Bot API via httpx."""

    BASE_URL = "https://api.telegram.org/bot"

    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.configured:
            logger.warning("Telegram não configurado — defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID")
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.BASE_URL}{self.token}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                    },
                )
                resp.raise_for_status()
                logger.info("Mensagem Telegram enviada com sucesso")
                return True
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem Telegram: {e}")
            return False

    def format_prediction(self, pred: dict) -> str:
        """Formata uma previsão para envio via Telegram."""
        m = pred.get("match", {})
        lines = [
            f"⚽ <b>{m.get('home_team', '?')} vs {m.get('away_team', '?')}</b>",
            f"🏆 {m.get('competition', '')}",
            "",
        ]
        po = pred.get("poisson")
        if po:
            lines.append("📊 <b>Probabilidades (Poisson):</b>")
            lines.append(f"  🏠 Casa: {po['home_win_prob']*100:.1f}%")
            lines.append(f"  🤝 Empate: {po['draw_prob']*100:.1f}%")
            lines.append(f"  ✈️ Fora: {po['away_win_prob']*100:.1f}%")
            lines.append(f"  ⬆️ Over 2.5: {po['over_25_prob']*100:.1f}%")
            lines.append(f"  🎯 BTTS: {po['btts_prob']*100:.1f}%")
            lines.append("")

        if pred.get("recommended_bet"):
            lines.append(f"💰 <b>Aposta:</b> {pred['recommended_bet']}")
            lines.append(f"📈 <b>Mercado:</b> {pred.get('recommended_market', '-')}")
            lines.append(f"🎯 <b>Confiança:</b> {pred.get('confidence', 0)}%")

        hf = pred.get("home_form", [])
        af = pred.get("away_form", [])
        if hf:
            lines.append(f"\n📋 Forma {m.get('home_team','')}: {''.join(hf)}")
        if af:
            lines.append(f"📋 Forma {m.get('away_team','')}: {''.join(af)}")

        return "\n".join(lines)

    def format_daily_summary(self, predictions: list[dict]) -> str:
        """Formata resumo diário com todas as previsões."""
        lines = [
            "🕌 <b>SHEIK DAS APOSTAS — Previsões do Dia</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]
        for i, p in enumerate(predictions[:10], 1):
            m = p.get("match", {})
            conf = p.get("confidence", 0)
            bet = p.get("recommended_bet", "-")
            stars = "⭐" * (3 if conf >= 65 else 2 if conf >= 45 else 1)
            lines.append(
                f"{i}. {m.get('home_team','?')} vs {m.get('away_team','?')}"
            )
            lines.append(f"   💰 {bet} | 🎯 {conf}% {stars}")
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🌐 sheikdasapostas.com.br")
        return "\n".join(lines)


telegram_service = TelegramService()
