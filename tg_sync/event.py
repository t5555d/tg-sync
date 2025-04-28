from enum import Enum

from pyrogram.enums import ChatType, MessageMediaType

EVENT_FIELDS = frozenset({
    "account_id",
    "message_id",
    "type_id",
    "date",
    "text",

    "chat_id",
    "chat_type",
    "chat_title",
    "chat_username",
    "chat_fullname",

    "user_id",
    "user_name",
    "user_fullname",
})


def _concat_optional(*args):
    non_empty_args = [arg for arg in args if arg]
    return " ".join(non_empty_args) if non_empty_args else None


def fill_event(event=None, message=None, account=None, chat=None, user=None):
    if event is None:
        event = {}

    if message:
        event.update({
            "message_id": message.id,
            "type_id": getattr(message.media, "value", None),
            "date": message.date,
            "text": message.text,
        })

    if account:
        event.update({
            "account_id": account.id,
        })

    if chat:
        event.update({
            "chat_id": chat.id,
            "chat_type": chat.type.value,
            "chat_title": chat.title,
            "chat_username": chat.username,
            "chat_fullname": _concat_optional(chat.first_name, chat.last_name),
        })

    if user:
        event.update({
            "user_id": user.id,
            "user_name": user.username,
            "user_fullname": _concat_optional(user.first_name, user.last_name),
        })

    return event
