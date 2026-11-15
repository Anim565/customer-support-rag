
from src.data_preparation.whatsapp_parser import (
    parse_whatsapp_message,
    parse_whatsapp_chat,
    audit_whatsapp_chat,
)


def test_android_message():

    message = (
        "15/11/2026, 09:31 - Client: "
        "Do you offer Hb electrophoresis?"
    )

    result = parse_whatsapp_message(message)

    assert result["sender"] == "Client"
    assert result["time"] == "09:31"
    assert result["message"] == "Do you offer Hb electrophoresis?"


def test_iphone_message():

    message = (
        "[15/11/2026, 09:32:00] Client: "
        "What is the turnaround time?"
    )

    result = parse_whatsapp_message(message)

    assert result["sender"] == "Client"
    assert result["time"] == "09:32"


def test_multiline_message():

    chat = """15/11/2026, 09:30 - Client: Kindly confirm:
1. Full Blood Count
2. HbA1c
15/11/2026, 09:35 - Laboratory: Available."""

    results = parse_whatsapp_chat(chat)

    assert len(results) == 2
    assert "Full Blood Count" in results[0]["message"]
    assert "HbA1c" in results[0]["message"]


def test_invalid_message():

    result = parse_whatsapp_message(
        "This is not a valid WhatsApp message"
    )

    assert result is None


def test_system_message_not_appended_to_customer():

    chat = """15/11/2026, 09:30 - Client: Good morning
15/11/2026, 09:31 - Client joined using this group's invite link
15/11/2026, 09:32 - Laboratory: How can we help?"""

    results = parse_whatsapp_chat(chat)

    assert len(results) == 2

    assert results[0]["message"] == "Good morning"

    assert results[1]["message"] == "How can we help?"



def test_chat_audit():

    chat = """15/11/2026, 09:30 - Client: Good morning
15/11/2026, 09:31 - Client joined using this group's invite link
15/11/2026, 09:32 - Laboratory: How can we help?"""

    result = audit_whatsapp_chat(chat)

    assert result["user_messages"] == 2
    assert result["other_timestamped_records"] == 1
    assert result["total_timestamped_records"] == 3
