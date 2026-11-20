
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



def classify_whatsapp_record(line):
    """
    Classify a timestamped WhatsApp record.

    Returns USER_MESSAGE, SYSTEM_EVENT,
    UNRECOGNIZED, or CONTINUATION.
    """

    if parse_whatsapp_message(line) is not None:
        return "USER_MESSAGE"

    if not is_timestamped_record(line):
        return "CONTINUATION"

    system_patterns = [
        r"joined using this group's invite link",
        r"left the group",
        r"was added",
        r"was removed",
        r"messages and calls are end-to-end encrypted",
        r"changed the group description",
        r"changed this group's icon",
    ]

    for pattern in system_patterns:
        if re.search(pattern, line, re.IGNORECASE):
            return "SYSTEM_EVENT"

    return "UNRECOGNIZED"



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


def audit_whatsapp_records(chat_text):
    """
    Audit WhatsApp record classifications.

    Returns counts and records requiring review.
    """

    counts = {
        "USER_MESSAGE": 0,
        "SYSTEM_EVENT": 0,
        "UNRECOGNIZED": 0,
    }

    unrecognized_records = []

    for line in chat_text.splitlines():

        category = classify_whatsapp_record(line)

        if category in counts:
            counts[category] += 1

        if category == "UNRECOGNIZED":
            unrecognized_records.append(line)

    return {
        "counts": counts,
        "unrecognized_records": unrecognized_records,
        "total_records": sum(counts.values()),
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
