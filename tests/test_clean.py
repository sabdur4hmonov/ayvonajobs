"""processing/clean.py: source_rules.yaml applied to the original text."""

from __future__ import annotations

import pytest

from ayvona.config import (
    DEFAULT_CONFIG_DIR,
    SourceRule,
    SourceRuleDefaults,
    SourceRulesConfig,
    load_settings,
)
from ayvona.processing.clean import Cleaner
from tests.post_fixtures import load_dir, to_post

DEFAULTS = SourceRuleDefaults(
    drop_link_patterns=["t.me/addlist/", "t.me/+", "instagram.com"],
    strip_url_params=["utm_source", "utm_medium", "text"],
    strip_lines=["kanalga obuna bo'ling"],
)


def make(rule: SourceRule | None = None) -> Cleaner:
    return Cleaner(SourceRulesConfig(defaults=DEFAULTS, sources={"@kanal": rule or SourceRule()}))


BODY = "Sotuvchi kerak\nMaosh: 4 000 000 so'm\nManzil: Chilonzor\nTel: +998 90 123 45 67"


def test_cut_from_removes_footer_and_keeps_emoji() -> None:
    c = make(SourceRule(cut_from=["ish kanallari to'plami"]))
    text = f"🔥 {BODY}\n\n📂 Ish kanallari to'plami:\nt.me/addlist/abc\nInstagram"
    out = c.clean(text, source="@kanal")
    assert out.text == f"🔥 {BODY}"
    assert out.removed_lines == 3


def test_cut_from_is_skipped_when_it_would_remove_most_of_the_text() -> None:
    c = make(SourceRule(cut_from=["sotuvchi kerak"]))  # matches the very first line
    out = c.clean(BODY, source="@kanal")
    assert out.text == BODY
    assert out.cut_skipped


def test_strip_exact_header_lines_and_trailing_hashtags() -> None:
    rule = SourceRule(
        strip_lines=["obuna bo'ling: @kanal"],
        exact_lines=["telegram"],
        header_lines=["✅✅✅✅"],
        drop_trailing_hashtags=True,
    )
    text = f"✅✅✅✅\n{BODY}\nTelegram\nKanalga obuna bo'ling!\n\n#sotuv #toshkent"
    assert make(rule).clean(text, source="@kanal").text == BODY


def test_tracking_parameters_are_removed_from_urls() -> None:
    text = f"{BODY}\nAriza: https://hh.uz/vacancy/1?utm_source=tg&utm_medium=x&id=5"
    extra = {"links": [{"text": "havola", "url": "https://t.me/hr_bot?start=1&text=salom"}]}
    out = make().clean(text + "\nhavola", extra, source="@kanal")
    assert "https://hh.uz/vacancy/1?id=5" in out.text
    assert "utm_" not in out.text
    assert out.links[0].url == "https://t.me/hr_bot?start=1"


def test_contacts_are_never_removed() -> None:
    # the HR's phone and username sit in the line a cut_from rule matches
    c = make(SourceRule(cut_from=["murojaat uchun"]))
    text = f"{BODY}\n\nMurojaat uchun: +998 91 555 44 33, @hr_kadr\nKanalga obuna bo'ling"
    out = c.clean(text, source="@kanal", own_usernames=["@kanal"])
    assert "+998 91 555 44 33" in out.text and "@hr_kadr" in out.text
    assert out.restored_lines == 1
    assert "obuna" not in out.text


def test_own_usernames_are_not_protected() -> None:
    c = make(SourceRule(strip_lines=["e'lon joylash"], extra_own_usernames=["@kanal_admin"]))
    text = f"{BODY}\nE'lon joylash: @kanal_admin"
    out = c.clean(text, source="@kanal")
    assert out.text == BODY and out.restored_lines == 0


def test_hidden_links_ads_and_removed_lines_are_dropped() -> None:
    c = make(SourceRule(cut_from=["bizning kanallar"]))
    text = f"{BODY}\nAriza: havola\n\nBizning kanallar 👇\nPapka"
    extra = {
        "links": [
            {"text": "havola", "url": "https://forms.gle/abc"},
            {"text": "  ", "url": "https://t.me/reklama_kanal/5"},  # whitespace: hidden ad
            {"text": "Papka", "url": "https://t.me/addlist/xyz"},
        ],
        "buttons": [{"text": "Apply here", "url": "https://example.com/apply?utm_source=a"}],
    }
    out = c.clean(text, extra, source="@kanal")
    assert [(lk.text, lk.url, lk.button) for lk in out.links] == [
        ("havola", "https://forms.gle/abc", False),
        ("Apply here", "https://example.com/apply", True),
    ]


def test_bot_added_channel_gets_only_defaults() -> None:
    c = make(SourceRule(strip_lines=["maosh"]))  # a (silly) channel rule
    text = f"{BODY}\nKanalga obuna bo'ling"
    assert "Maosh" not in c.clean(text, source="@kanal").text
    only = c.clean(text, source="@kanal", only_defaults=True).text
    assert "Maosh" in only and "obuna" not in only


# ------------------------------------------------------------------ real posts
REAL = [fx for fx in load_dir() if fx["expected"]["kind"] == "job"]


@pytest.fixture(scope="module")
def cleaner() -> Cleaner:
    return Cleaner(load_settings(DEFAULT_CONFIG_DIR, env_file=None).source_rules)


@pytest.mark.parametrize("fx", REAL, ids=[fx["id"] for fx in REAL])
def test_real_posts_keep_their_contacts(cleaner: Cleaner, fx: dict) -> None:
    post = to_post(fx)
    out = cleaner.clean(post.text, post.extra, source=post.source, own_usernames=post.own_usernames)
    assert out.text
    exp = fx["expected"]
    folded = out.text.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    for phone in exp.get("phones", []):
        tail = phone[-7:]
        assert tail in folded.replace(".", ""), phone
    for user in exp.get("usernames", []):
        in_text = user.lower() in out.text.lower()
        in_links = any(user.lstrip("@").lower() in lk.url.lower() for lk in out.links)
        assert in_text or in_links or user.lower() not in post.text.lower(), user
