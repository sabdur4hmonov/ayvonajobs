"""Bosqich 15: the optional Gemini helper. Nothing is sent anywhere: the HTTP client is an
``httpx.MockTransport`` or a fake, and the pipeline must publish the job in every failure case."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from ayvona.ai.client import (
    AIBadResponse,
    AIError,
    AIRateLimited,
    AIUnavailable,
    GeminiClient,
)
from ayvona.ai.helper import AIHelper, mask, set_admin_disabled
from ayvona.config import Settings
from ayvona.db.models import Job, ParseMethod, RawPostStatus
from ayvona.processing.classify import PostInput
from ayvona.processing.extract import Extractor
from ayvona.processing.language import Language
from ayvona.processing.pipeline import Pipeline
from tests.test_admin_bot import BotHarness, callback_update, message_update
from tests.test_public_bot import bot_settings
from tests.worker_helpers import SF, add_raw, add_source, get_raw, make_settings

RU_POST = (
    "Требуется продавец-консультант\n"
    "Зарплата: от 5 000 000 сум\n"
    "Адрес: г. Ташкент, Чиланзар\n"
    "Требования: опыт работы от 1 года, знание узбекского языка\n"
    "Тел: +998 90 123 45 67"
)
GOOD = {
    "is_job": True,
    "title": "Sotuvchi-konsultant",
    "company": None,
    "category": "sotuv",
    "salary_min": 5_000_000,
    "salary_max": None,
    "currency": "UZS",
    "salary_period": "month",
    "salary_text": None,
    "region": "toshkent_sh",
    "city": "Chilonzor",
    "is_remote": False,
    "schedule": None,
    "requirements": "1 yildan ortiq tajriba; o'zbek tilini bilish",
    "short_description": None,
}


def ai_settings(**ai: Any) -> Settings:
    s = make_settings(publisher={"hold_minutes": 0})
    env = s.env.model_copy(
        update={
            "gemini_api_key": SecretStr("KEY-ONE"),
            "gemini_api_keys": SecretStr("KEY-TWO, KEY-THREE"),
        }
    )
    app = s.app.model_copy(
        update={"ai": s.app.ai.model_copy(update={"min_interval_seconds": 0, **ai})}
    )
    return s.model_copy(update={"env": env, "app": app})


class FakeClient:
    """Stands in for GeminiClient: records calls, answers from a script."""

    def __init__(self, *answers: dict[str, Any] | Exception) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[str, str]] = []

    async def generate_json(
        self, api_key: str, system: str, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        self.calls.append((api_key, prompt))
        answer = self.answers.pop(0) if self.answers else GOOD
        if isinstance(answer, Exception):
            raise answer
        return answer


def extraction(settings: Settings, text: str = RU_POST):  # noqa: ANN201
    return Extractor(settings).extract(PostInput(text=text, source="@kanal"))


# ------------------------------------------------------------------ masking / client
def test_contacts_never_leave_the_machine() -> None:
    masked = mask("Тел: +998 90 123-45-67, 901234567, @hr_boss, a@b.uz, https://t.me/x hh.uz")
    assert "90" not in masked.replace("[PHONE]", "")
    assert "@hr_boss" not in masked and "a@b.uz" not in masked and "t.me" not in masked
    assert masked.count("[PHONE]") == 2


def _client(handler: Any) -> GeminiClient:
    return GeminiClient("test-model", transport=httpx.MockTransport(handler))


async def test_client_success_and_request_shape() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers["x-goog-api-key"]
        seen["body"] = json.loads(request.content)
        answer = {"candidates": [{"content": {"parts": [{"text": json.dumps(GOOD)}]}}]}
        return httpx.Response(200, json=answer)

    data = await _client(handler).generate_json("K", "sys", "matn", {"type": "OBJECT"})
    assert data["title"] == "Sotuvchi-konsultant"
    assert "models/test-model:generateContent" in seen["url"] and seen["key"] == "K"
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx.Response(429, json={}), AIRateLimited),
        (httpx.Response(503, json={}), AIUnavailable),
        (httpx.Response(200, json={"candidates": []}), AIBadResponse),
        (
            httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{no"}]}}]}),
            AIBadResponse,
        ),
    ],
)
async def test_client_errors(response: httpx.Response, error: type[AIError]) -> None:
    with pytest.raises(error):
        await _client(lambda _: response).generate_json("K", "s", "p", {})


async def test_client_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(AIUnavailable):
        await _client(handler).generate_json("K", "s", "p", {})


# ------------------------------------------------------------------ helper
async def test_russian_post_translated_contacts_kept(session_factory: SF) -> None:
    st = ai_settings()
    fake = FakeClient(GOOD)
    helper = AIHelper(st, session_factory, fake)  # type: ignore[arg-type]
    ex = extraction(st)
    assert ex.language is Language.RU and helper.wanted(ex)

    better = await helper.enhance(RU_POST, ex)
    assert better is not None and better.ai_used
    assert better.title == "Sotuvchi-konsultant" and better.language is Language.UZ_LATIN
    assert better.phones == ex.phones == ("+998901234567",)  # always from regex
    assert better.requirements and "tajriba" in better.requirements
    [(key, prompt)] = fake.calls
    assert key == "KEY-ONE"  # rotation off: only the first key
    assert "+998" not in prompt and "[PHONE]" in prompt

    again = await helper.enhance(RU_POST, ex)  # cached: no second request
    assert again is not None and len(fake.calls) == 1
    status = await helper.status()
    assert status.calls_today == 1 and status.ok_today == 1 and status.cache_hits_today == 1


async def test_uzbek_confident_post_is_not_sent(session_factory: SF) -> None:
    st = ai_settings()
    fake = FakeClient()
    text = "Sotuvchi kerak\nMaosh: 5 000 000 so'm\nManzil: Toshkent, Chilonzor\nTel: +998901234567"
    ex = extraction(st, text)
    assert await AIHelper(st, session_factory, fake).enhance(text, ex) is None  # type: ignore[arg-type]
    assert fake.calls == []


@pytest.mark.parametrize(
    "bad",
    [
        {**GOOD, "title": "Продавец"},  # Cyrillic left
        {**GOOD, "title": ""},
        {
            **GOOD,
            "requirements": "At least one year of experience in retail sales and good English "
            "communication skills are required for this position",
        },
    ],
)
async def test_bad_answers_are_dropped(session_factory: SF, bad: dict[str, Any]) -> None:
    st = ai_settings()
    helper = AIHelper(st, session_factory, FakeClient(bad))  # type: ignore[arg-type]
    assert await helper.enhance(RU_POST, extraction(st)) is None


async def test_rate_limit_pauses_the_key_then_rotation(session_factory: SF) -> None:
    st = ai_settings()
    fake = FakeClient(AIRateLimited("429"))
    helper = AIHelper(st, session_factory, fake)  # type: ignore[arg-type]
    assert await helper.enhance(RU_POST, extraction(st)) is None
    assert await helper.enhance(RU_POST + "\n2", extraction(st)) is None  # key paused: no call
    assert len(fake.calls) == 1 and (await helper.status()).paused

    rot = st.model_copy(
        update={"env": st.env.model_copy(update={"gemini_allow_key_rotation": True})}
    )
    fake2 = FakeClient(AIRateLimited("429"), GOOD)
    helper2 = AIHelper(rot, session_factory, fake2)  # type: ignore[arg-type]
    assert helper2.keys == ["KEY-ONE", "KEY-TWO", "KEY-THREE"]
    assert await helper2.enhance(RU_POST + "\n3", extraction(rot)) is None  # KEY-ONE was paused
    # KEY-ONE is paused (from above) -> KEY-TWO: 429 -> then KEY-THREE works
    assert await helper2.enhance(RU_POST + "\n4", extraction(rot)) is not None
    assert [k for k, _ in fake2.calls] == ["KEY-TWO", "KEY-THREE"]


async def test_daily_limit_and_admin_switch(session_factory: SF) -> None:
    st = ai_settings(daily_limit=1)
    fake = FakeClient()
    helper = AIHelper(st, session_factory, fake)  # type: ignore[arg-type]
    assert await helper.enhance(RU_POST, extraction(st)) is not None
    assert await helper.enhance(RU_POST + "\nx", extraction(st)) is None  # limit
    assert len(fake.calls) == 1

    async with session_factory() as s, s.begin():
        await set_admin_disabled(s, True)
    assert await helper.enhance(RU_POST, extraction(st)) is None  # even the cache is off
    assert (await helper.status()).active is False


async def test_no_key_means_no_ai(session_factory: SF) -> None:
    st = make_settings()
    fake = FakeClient()
    helper = AIHelper(st, session_factory, fake)  # type: ignore[arg-type]
    assert helper.keys == [] and await helper.enhance(RU_POST, extraction(st)) is None
    assert fake.calls == []


# ------------------------------------------------------------------ pipeline
@pytest.mark.parametrize(
    "answer", [GOOD, AIUnavailable("timeout"), AIRateLimited("429"), AIBadResponse("json")]
)
async def test_pipeline_always_publishes(session_factory: SF, answer: Any) -> None:
    st = ai_settings()
    src = await add_source(session_factory)
    raw = await add_raw(session_factory, src, RU_POST)
    helper = AIHelper(st, session_factory, FakeClient(answer))  # type: ignore[arg-type]
    await Pipeline(st, session_factory, ai=helper).run_once()

    row = await get_raw(session_factory, raw)
    assert row.status is RawPostStatus.DONE
    async with session_factory() as s:
        job = (await s.scalars(select(Job))).one()
    assert job.contact_phone == "+998901234567"
    text = job.formatted_text or ""
    assert not any("Ѐ" <= ch <= "ӿ" for ch in text)
    if answer is GOOD:
        assert job.parse_method is ParseMethod.GEMINI
        assert "💼 <b>Sotuvchi-konsultant</b>" in text and "tajriba" in text
    else:
        assert job.parse_method is not ParseMethod.GEMINI


# ------------------------------------------------------------------ /ai
@pytest.fixture
def harness(tmp_path: Path, session_factory: SF) -> BotHarness:
    return BotHarness(bot_settings(tmp_path), session_factory)


async def test_ai_admin_command(harness: BotHarness, session_factory: SF) -> None:
    await harness.send(message_update("/ai"))
    assert "kalit yo'q" in harness.texts()[-1]

    st = ai_settings()
    st = st.model_copy(update={"env": st.env.model_copy(update={"admin_ids": [111]})})
    h = BotHarness(st, session_factory)
    await h.send(message_update("/ai"))
    assert "ishlayapti" in h.texts()[-1] and "0/200" in h.texts()[-1]
    await h.send(callback_update("ai:off"))
    assert "admin o'chirgan" in h.texts()[-1]
    await h.send(callback_update("ai:on"))
    assert "ishlayapti" in h.texts()[-1]
    await h.send(message_update("/stats"))
    assert "AI bugun: 0/200" in h.texts()[-1]


# ------------------------------------------------------------------ free-tier guards (deploy)
async def _pause_until(sf: SF, key: int = 0) -> Any:
    from ayvona.db.repositories import kv_repo

    async with sf() as s:
        return await kv_repo.get_time(s, f"ai:pause:{key}")


async def test_pause_doubles_after_repeated_429_and_resets_after_a_success(
    session_factory: SF,
) -> None:
    from datetime import timedelta

    from ayvona.timeutil import utcnow

    st = ai_settings(pause_minutes_rate_limited=10, pause_minutes_max=60)
    limited = AIRateLimited("429")
    fake = FakeClient(limited, limited, limited, limited, GOOD, limited)
    helper = AIHelper(st, session_factory, fake)  # type: ignore[arg-type]
    now = utcnow()
    minutes: list[float] = []
    for i in range(4):  # 429 four times in a row: 10, 20, 40, then capped at 60
        assert await helper.enhance(f"{RU_POST}\n{i}", extraction(st), now=now) is None
        until = await _pause_until(session_factory)
        minutes.append((until - now).total_seconds() / 60)
        now = until + timedelta(seconds=1)  # the key is awake again
    assert minutes == [10, 20, 40, 60]

    assert await helper.enhance(f"{RU_POST}\nok", extraction(st), now=now) is not None  # success
    assert await helper.enhance(f"{RU_POST}\nnext", extraction(st), now=now) is None  # 429 again
    until = await _pause_until(session_factory)
    assert (until - now).total_seconds() / 60 == 10  # backoff started over


async def test_retry_after_is_honoured(session_factory: SF) -> None:
    from ayvona.timeutil import utcnow

    st = ai_settings(pause_minutes_rate_limited=10)
    fake = FakeClient(AIRateLimited("429", retry_after=2 * 3600))
    helper = AIHelper(st, session_factory, fake)  # type: ignore[arg-type]
    now = utcnow()
    assert await helper.enhance(RU_POST, extraction(st), now=now) is None
    assert (await _pause_until(session_factory) - now).total_seconds() / 60 == 120


async def test_client_reads_retry_after_header() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "30"}, json={})

    with pytest.raises(AIRateLimited) as info:
        await _client(handler).generate_json("K", "s", "p", {})
    assert info.value.retry_after == 30

    def date_handler(_: httpx.Request) -> httpx.Response:  # an HTTP date is not parsed: ignored
        return httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})

    with pytest.raises(AIRateLimited) as info2:
        await _client(date_handler).generate_json("K", "s", "p", {})
    assert info2.value.retry_after is None


async def test_env_overrides_the_daily_cap_and_interval(session_factory: SF) -> None:
    st = ai_settings(daily_limit=100, min_interval_seconds=0)
    st = st.model_copy(
        update={
            "env": st.env.model_copy(
                update={"gemini_daily_limit": 1, "gemini_min_interval_seconds": 7}
            )
        }
    )
    fake = FakeClient()
    helper = AIHelper(st, session_factory, fake)  # type: ignore[arg-type]
    assert (helper.cfg.daily_limit, helper.cfg.min_interval_seconds) == (1, 7)
    assert await helper.enhance(RU_POST, extraction(st)) is not None
    assert await helper.enhance(RU_POST + "\nx", extraction(st)) is None  # env cap reached
    assert len(fake.calls) == 1 and (await helper.status()).daily_limit == 1


def test_blank_env_limits_mean_not_set() -> None:
    from ayvona.config import EnvSettings

    env = EnvSettings(_env_file=None, gemini_daily_limit="", gemini_min_interval_seconds=" ")  # type: ignore[arg-type,call-arg]
    assert env.gemini_daily_limit is None and env.gemini_min_interval_seconds is None
