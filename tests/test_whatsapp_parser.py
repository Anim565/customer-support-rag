
from src.data_preparation.whatsapp_parser import (
    parse_whatsapp_message,
    parse_whatsapp_chat,
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
