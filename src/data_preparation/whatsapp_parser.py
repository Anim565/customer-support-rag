
import re



def parse_whatsapp_message(line):
    """
    Parse a WhatsApp message header.

    Supports selected Android and iPhone formats.
    Returns a dictionary or None.
    """

    patterns = [
        # Android-style export
        r"^(\d{1,2}/\d{1,2}/\d{4}), "
        r"(\d{1,2}:\d{2}) - "
        r"([^:]+): (.*)$",

        # iPhone-style export
        r"^\[(\d{1,2}/\d{1,2}/\d{4}), "
        r"(\d{1,2}:\d{2})(?::\d{2})?\] "
        r"([^:]+): (.*)$"
    ]

    for pattern in patterns:
        match = re.match(pattern, line)

        if match is not None:
            return {
                "date": match.group(1),
                "time": match.group(2),
                "sender": match.group(3),
                "message": match.group(4)
            }

    return None



def parse_whatsapp_chat(chat_text):
    """
    Parse an entire WhatsApp conversation.

    Supports messages that span multiple lines.
    """

    messages = []
    current_message = None

    for line in chat_text.splitlines():

        parsed = parse_whatsapp_message(line)

        if parsed is not None:

            if current_message is not None:
                messages.append(current_message)

            current_message = parsed

        elif current_message is not None:

            current_message["message"] += "\n" + line

    if current_message is not None:
        messages.append(current_message)

    return messages




if __name__ == "__main__":

    android_message = (
        "15/11/2026, 09:31 - Client: "
        "Do you offer Hb electrophoresis?"
    )

    iphone_message = (
        "[15/11/2026, 09:32:00] Client: "
        "What is the turnaround time?"
    )

    print("ANDROID TEST")
    print(parse_whatsapp_message(android_message))

    print("\nIPHONE TEST")
    print(parse_whatsapp_message(iphone_message))
