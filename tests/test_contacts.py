import pytest

from ayvona.processing.contacts import canon_username, find_contacts, find_phones, linked_positions
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


@pytest.mark.parametrize(
    "raw", ["4 000 000 so'm", "7 500 000 - 15 000 000", "2026-09-19", "920012700"]
)
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
    c = find_contacts(
        normalize("@JahongirAcademy_admin va @JahongirAcademy"), own_usernames=["@JahongirAcademy"]
    )
    assert c.usernames == ["@jahongiracademy_admin"]


def test_canon_username() -> None:
    assert canon_username("https://t.me/Foo_Bar?start=1") == "@foo_bar"
    assert canon_username("@Foo") == "@foo"


# ------------------------------------------------------------------ Bosqich 5
def test_unknown_code_needs_a_contact_word() -> None:
    assert find_phones("buyurtma raqami 30 123 45 67") == []
    assert find_phones("Tel: 30 123 45 67") == ["+998301234567"]
    assert find_phones("+998 30 123 45 67") == ["+998301234567"]  # the prefix is proof enough


def test_digits_inside_links_are_not_phones() -> None:
    assert find_phones("https://tashkent.hh.uz/vacancy/137865831") == []


def test_apply_url_choice_and_cleaning() -> None:
    extra = {
        "links": [
            {"text": "Jobs", "url": "https://jobs.example.com/"},  # footer: not an apply link
            {"text": "Instagram", "url": "https://instagram.com/x"},
            {"text": "havola", "url": "https://t.me/naxalov/2559"},  # a channel post
        ],
        "buttons": [
            {"text": "📝 Apply here", "url": "https://b.example.com/track/apply/1?source=telegram"}
        ],
    }
    c = find_contacts("", extra, strip_url_params=["source"])
    assert c.urls == ["https://b.example.com/track/apply/1"]
    assert c.apply_url == "https://b.example.com/track/apply/1"


def test_keep_case_usernames() -> None:
    extra = {"links": [{"text": "Get the job.", "url": "http://t.me/HR_KONIDA"}]}
    c = find_contacts("Telegram: @Dilnozaa_brand", extra, keep_case=True)
    assert c.usernames == ["@Dilnozaa_brand", "@HR_KONIDA"]
    assert c.keys == {"@dilnozaa_brand", "@hr_konida"}


def test_linked_positions() -> None:
    text = (
        "Bank jamoasi\n🔗 Tarmoq administratori (havola)\n🔗 Java dasturchi (havola)\n🚀 Telegram"
    )
    links = [
        {"text": "(havola)", "url": "https://hh.uz/vacancy/1"},
        {"text": "(havola)", "url": "https://hh.uz/vacancy/2"},
        {"text": "Telegram", "url": "https://t.me/bank"},
    ]
    found = linked_positions(text, {"links": links})
    assert [u for _, u in found] == ["https://hh.uz/vacancy/1", "https://hh.uz/vacancy/2"]
