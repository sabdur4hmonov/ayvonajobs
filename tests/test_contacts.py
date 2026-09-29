import pytest

from ayvona.processing.contacts import canon_username, find_contacts, find_phones
from ayvona.processing.normalize import normalize


@pytest.mark.parametrize(
    ("raw", "phone"),
    [
        ("+998901171112", "+998901171112"),
        ("+998 50 977 33 36", "+998509773336"),
        ("+998-90-996-97-77", "+998909969777"),
        ("+99897 425 28 87", "+998974252887"),
        ("998-90-068-41-70", "+998900684170"),
        ("953538444", "+998953538444"),
        ("772701545", "+998772701545"),
        ("88-401-12-30", "+998884011230"),
        ("87-805-33-33", "+998878053333"),
        ("33 077 14 03", "+998330771403"),
        ("97.798 67 22", "+998977986722"),
        ("(97) 137-16-94", "+998971371694"),
        ("🔔99)208-65-53", "+998992086553"),
        ("Telegram: +998 333378888", "+998333378888"),
        ("t.me/+998996552224", "+998996552224"),
    ],
)
def test_phone_spellings(raw: str, phone: str) -> None:
    assert find_phones(normalize(raw)) == [phone]


@pytest.mark.parametrize("raw", ["4 000 000 so'm", "7 500 000 - 15 000 000", "2026-09-19", "920012700"])
def test_not_phones(raw: str) -> None:
    assert find_phones(normalize(raw)) == []


def test_contacts_from_text_and_hidden_links() -> None:
    text = normalize("Murojaat: +998 90 939 51 29\n@HRFlink\nxat: rustamjon.business@gmail.com")
    extra = {
        "links": [
            {"text": "Get the job.", "url": "http://t.me/HR_KONIDA"},
            {"text": "\n", "url": "https://t.me/JahongirAcademy/2432"},  # whitespace text -> ad
            {"text": "Telegram", "url": "https://t.me/ishlaUZ_rasmiy"},  # the channel itself
            {"text": "Instagram", "url": "https://www.instagram.com/x"},
        ],
        "buttons": [{"text": "📝 Apply here", "url": "https://backend.example.com/apply/1"}],
    }
    c = find_contacts(
        text,
        extra,
        own_usernames=["@ishlaUZ_rasmiy"],
        drop_link_patterns=["instagram.com", "t.me/+"],
    )
    assert c.phones == ["+998909395129"]
    assert c.usernames == ["@hrflink", "@hr_konida"]
    assert c.emails == ["rustamjon.business@gmail.com"]
    assert c.urls == ["https://backend.example.com/apply/1"]
    assert c.first == "+998909395129"


def test_email_is_not_a_username_but_dot_before_at_is() -> None:
    c = find_contacts(normalize("CV: rustamjon.business@gmail.com, sms.@ainna_hr"))
    assert c.usernames == ["@ainna_hr"]


def test_bot_deep_link_is_apply_url_not_username() -> None:
    extra = {"buttons": [{"text": "Qiziqish", "url": "https://t.me/fba_connect_bot?start=vak7"}]}
    c = find_contacts("", extra)
    assert c.usernames == []
    assert c.urls == ["https://t.me/fba_connect_bot?start=vak7"]


def test_own_usernames_exact_match() -> None:
    c = find_contacts(normalize("@JahongirAcademy_admin va @JahongirAcademy"), own_usernames=["@JahongirAcademy"])
    assert c.usernames == ["@jahongiracademy_admin"]


def test_canon_username() -> None:
    assert canon_username("https://t.me/Foo_Bar?start=1") == "@foo_bar"
    assert canon_username("@Foo") == "@foo"
