import hashlib
import hmac
import json
import logging
import time
from collections import OrderedDict
from collections.abc import Callable

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from .chatwoot import ChatwootClient, Inbox
from .hours import BusinessHours
from .knowledge import Retriever, load_chunks
from .llm import LLM, FakeLLM, OpenAICompatLLM
from .service import SupportBot
from .settings import Settings
from .usage import UsageCap
from .webhook import parse_event

MAX_SIGNATURE_AGE_S = 300
MAX_SEEN_DELIVERIES = 10_000
log = logging.getLogger("support_bot")


def configure_logging() -> None:
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False


def signature_ok(key: str, raw: bytes, ts: str | None, signature: str | None, now: float) -> bool:
    if not ts or not signature or not signature.isascii() or not ts.isdigit() or abs(now - int(ts)) > MAX_SIGNATURE_AGE_S:
        return False
    expected = "sha256=" + hmac.new(key.encode(), ts.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


class ReplayGuard:
    """Remembers recent delivery ids and signatures so a captured request cannot be replayed inside the window."""

    def __init__(self, ttl_s: float = 2 * MAX_SIGNATURE_AGE_S, max_items: int = MAX_SEEN_DELIVERIES):
        self.ttl_s, self.max_items = ttl_s, max_items
        self.seen: OrderedDict[str, float] = OrderedDict()

    def first_time(self, keys: list[str], now: float) -> bool:
        while self.seen and (next(iter(self.seen.values())) < now - self.ttl_s or len(self.seen) > self.max_items):
            self.seen.popitem(last=False)
        if any(k in self.seen for k in keys):
            return False
        for k in keys:
            self.seen[k] = now
        return True


def create_app(
    settings: Settings,
    chatwoot: Inbox | None = None,
    llm: LLM | None = None,
    wall_clock: Callable[[], float] = time.time,
) -> FastAPI:
    configure_logging()
    if not settings.webhook_secret:
        raise ValueError("BOT_WEBHOOK_SECRET is required")
    chunks = load_chunks(settings.knowledge_dir)
    if llm is None:
        llm = FakeLLM.default() if settings.fake_llm else OpenAICompatLLM(
            settings.llm_base_url,
            settings.llm_model,
            settings.llm_api_key,
            settings.llm_timeout,
            settings.llm_reasoning_effort,
            settings.llm_uds or None,
        )
    if chatwoot is None:
        chatwoot = ChatwootClient(settings.chatwoot_url, settings.chatwoot_bot_token, settings.chatwoot_team_id)
    cap = UsageCap(settings.usage_db, settings.max_calls_per_day, settings.max_tokens_per_day, settings.timezone)
    bot = SupportBot(
        Retriever(chunks), llm, cap, BusinessHours.default(settings.timezone), chatwoot, settings.top_k, settings.min_confidence
    )
    async def safe_handle(msg):
        try:
            await bot.handle(msg)
        except Exception:
            log.exception("failed to handle conversation %s", msg.conversation_id)

    replays = ReplayGuard()
    app = FastAPI(title="support-bot", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/healthz")
    def health():
        return {"status": "ok", "chunks": len(chunks), "llm": "fake" if settings.fake_llm else settings.llm_model}

    @app.post("/webhook/{secret}")
    async def webhook(secret: str, request: Request, background: BackgroundTasks):
        if not hmac.compare_digest(secret.encode(), settings.webhook_secret.encode()):
            raise HTTPException(status_code=404)
        raw = await request.body()
        if settings.webhook_hmac_secret and not signature_ok(
            settings.webhook_hmac_secret,
            raw,
            request.headers.get("x-chatwoot-timestamp"),
            request.headers.get("x-chatwoot-signature"),
            wall_clock(),
        ):
            raise HTTPException(status_code=401, detail="bad signature")
        keys = [f"{name}:{value}" for name, value in (
            ("delivery", request.headers.get("x-chatwoot-delivery")),
            ("signature", request.headers.get("x-chatwoot-signature") if settings.webhook_hmac_secret else None),
        ) if value]
        if keys and not replays.first_time(keys, wall_clock()):
            log.info("dropped replayed delivery")
            return {"status": "duplicate"}
        try:
            payload = json.loads(raw)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid json")
        msg = parse_event(payload)
        if msg is None:
            if isinstance(payload, dict):
                conv = payload.get("conversation") or {}
                log.debug(
                    "ignored event=%s message_type=%s status=%s assignee=%s",
                    payload.get("event"), payload.get("message_type"), conv.get("status"),
                    bool((conv.get("meta") or {}).get("assignee")),
                )
            return {"status": "ignored"}
        background.add_task(safe_handle, msg)
        return {"status": "accepted"}

    return app
