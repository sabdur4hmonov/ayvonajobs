"""Loyihalar: how a one-time paid project looks in the channel, and its buttons.

A project is NOT a job: it has a one-time budget instead of a salary, a deadline instead of a
schedule, and the channel post is clearly marked ``🧩 LOYIHA`` / ``#loyiha``. The caption is built
here (not by the job :class:`~ayvona.processing.formatter.Formatter`) from the form's answers; the
signature, phone / @username layout and the 1024-character limit are shared with it.
"""

from __future__ import annotations

from dataclasses import dataclass

from ayvona.config import Settings
from ayvona.processing.formatter import (
    CURRENCY_NAMES,
    T_PHONE,
    T_SEPARATOR,
    T_SIGN_BOT,
    T_SIGN_CHANNEL,
    T_TELEGRAM,
    esc,
    format_amount,
    format_phone,
    full_info_url,
    truncate,
    truncate_units,
    visible_len,
)
from ayvona.processing.normalize import fold
from ayvona.processing.salary import UZS, SalaryBlock, SalaryParser

PROJECT_TAG = "loyiha"
T_PROJECT = "🧩 <b>LOYIHA</b>"
T_BUDGET = "💰 Byudjet:"
T_BUDGET_ONCE = "(bir martalik)"
T_DEADLINE = "⏳ Muddat:"
T_NEGOTIABLE = "Kelishiladi"
B_CONTACT = "📩 Murojaat"
B_SAVE = "⭐ Saqlash"
B_MORE = "🧩 Boshqa loyihalar"
B_FULL_INFO = "📖 To'liq ma'lumot"
MAX_CAPTION = 1024  # Telegram: photo caption


@dataclass(frozen=True, slots=True)
class Budget:
    amount: int | None  # None = "Kelishiladi" or not understood
    currency: str | None
    text: str  # what the post shows: "3 000 000 so'm" / the user's own words / "Kelishiladi"


def parse_budget(raw: str | None, settings: Settings) -> Budget:
    """``"3 mln so'm"`` -> 3 000 000 UZS; ``"$300"`` -> 300 USD; ``None`` / anything without a
    number -> negotiable (the user's words are kept as typed). One-time: the period is ignored."""
    text = (raw or "").strip()
    if not text:
        return Budget(None, None, T_NEGOTIABLE)
    sal = SalaryParser(settings.extract).parse([SalaryBlock(display=text, folded=fold(text))])
    amount = (sal.min or sal.max) if sal else None
    if sal is None or not amount:
        return Budget(None, None, text)
    cur = sal.currency or UZS
    name = CURRENCY_NAMES.get(cur, cur)
    glue = "" if name == "so'm" else " "
    if sal.min and sal.max and sal.min != sal.max:
        shown = f"{format_amount(sal.min)} – {format_amount(sal.max)} {name}"
    else:
        shown = f"{format_amount(amount)} {name}"
    if sal.min and not sal.max or (sal.max and not sal.min):
        shown += f"{glue}dan" if sal.min else f"{glue}gacha"
    return Budget(amount, cur, shown)


@dataclass(frozen=True, slots=True)
class ProjectPost:
    html: str
    username: str | None  # first @username -> the "📩 Murojaat" button
    bot_username: str
    tags: tuple[str, ...] = (PROJECT_TAG,)
    # the bot's full card when the description was shortened ("📖 To'liq ma'lumot")
    full_html: str | None = None

    def buttons(self, job_id: int) -> list[list[dict[str, str]]]:
        first = (
            [{"text": B_CONTACT, "url": f"https://t.me/{self.username.lstrip('@')}"}]
            if self.username
            else []
        )
        full = (
            [{"text": B_FULL_INFO, "url": full_info_url(self.bot_username, job_id)}]
            if self.full_html
            else []
        )
        second = [
            {"text": B_SAVE, "url": f"https://t.me/{self.bot_username}?start=save_{job_id}"},
            {"text": B_MORE, "url": f"https://t.me/{self.bot_username}?start=projects"},
        ]
        return [row for row in (first, full, second) if row]


def format_project(
    *,
    title: str,
    description: str | None,
    budget: Budget,
    deadline: str | None,
    phone: str | None,
    username: str | None,
    settings: Settings,
) -> ProjectPost:
    """The channel caption of a project (HTML, at most 1024 characters)."""
    b = settings.app.branding
    head = [T_PROJECT, f"<b>{esc(truncate(title, 120))}</b>"]
    facts = [f"{T_BUDGET} {esc(budget.text)} {T_BUDGET_ONCE}".rstrip()]
    if deadline:
        facts.append(f"{T_DEADLINE} {esc(truncate(deadline, 120))}")
    contacts = []
    if phone:
        contacts.append(f"{T_PHONE} {format_phone(phone)}")
    if username:
        contacts.append(f"{T_TELEGRAM} {esc(username)}")
    tail = [
        f"#{PROJECT_TAG}",
        T_SEPARATOR,
        esc(T_SIGN_BOT.format(bot=b.bot_username)),
        esc(T_SIGN_CHANNEL.format(channel=b.channel_username, title=b.channel_title)),
    ]

    def build(body: str | None) -> str:
        blocks = [head, facts]
        if body:
            blocks.append([esc(body)])
        blocks += [contacts, tail]
        return "\n\n".join("\n".join(x) for x in blocks if x)

    text = (description or "").strip()
    caption = full = build(text or None)
    shortened = visible_len(caption) > MAX_CAPTION
    if shortened:  # shrink only the long free text (whole sentences), never the facts
        room = MAX_CAPTION - visible_len(build(None)) - 4
        caption = build(truncate_units(text, max(room, 0)) or None)
    return ProjectPost(
        html=caption,
        username=username,
        bot_username=b.bot_username,
        full_html=full if shortened else None,
    )
