
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


def is_timestamped_record(line):
    """
    Check whether a line begins with a recognized
    WhatsApp timestamp, with or without a sender.
    """

    patterns = [
        # Android-style timestamp
        r"^\d{1,2}/\d{1,2}/\d{4}, "
        r"\d{1,2}:\d{2} - ",

        # iPhone-style timestamp
        r"^\[\d{1,2}/\d{1,2}/\d{4}, "
        r"\d{1,2}:\d{2}(?::\d{2})?\] "
    ]

    return any(
        re.match(pattern, line) is not None
        for pattern in patterns
    )



def parse_whatsapp_chat(chat_text):
    """
    Parse a WhatsApp conversation.

    Preserve multiline messages while excluding
    timestamped records without recognized senders.
    """

    messages = []
    current_message = None

    for line in chat_text.splitlines():

        parsed = parse_whatsapp_message(line)

        if parsed is not None:

            if current_message is not None:
                messages.append(current_message)

            current_message = parsed

        elif is_timestamped_record(line):

            # Finish the previous message before
            # encountering a system record.
            if current_message is not None:
                messages.append(current_message)

            # Do not attach this record to a user message.
            current_message = None

        elif current_message is not None:

            # This is a continuation of the current message.
            current_message["message"] += "\n" + line

    if current_message is not None:
        messages.append(current_message)

    return messages


def audit_whatsapp_chat(chat_text):
    """
    Produce basic parsing statistics for a WhatsApp chat.

    Counts recognized user messages and timestamped
    records without a recognized sender.
    """

    user_messages = 0
    other_timestamped_records = 0

    for line in chat_text.splitlines():

        if parse_whatsapp_message(line) is not None:
            user_messages += 1

        elif is_timestamped_record(line):
            other_timestamped_records += 1

    return {
        "user_messages": user_messages,
        "other_timestamped_records": other_timestamped_records,
        "total_timestamped_records": (
            user_messages + other_timestamped_records
        )
    }



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
