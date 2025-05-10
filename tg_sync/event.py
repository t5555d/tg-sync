from telethon.types import Channel, Chat, User
from telethon.utils import get_input_location

from .utils import get_chat_id

EVENT_FIELDS = frozenset({
    "account_id",
    "message_id",
    "type_id",
    "date",
    "text",

    "chat_id",
    "chat_type",
    "chat_title",
    "chat_login",
    "chat_fullname",

    "user_id",
    "user_login",
    "user_fullname",
})

MEDIA_TYPES = [
    "audio",
    "gif",
    "photo",
    "sticker",
    "video",
    "video_note",
    "voice",
    "document",
]


def _concat_optional(*args):
    non_empty_args = [arg for arg in args if arg]
    return " ".join(non_empty_args) if non_empty_args else None


def _get_message_media_type(message):
    for type in MEDIA_TYPES:
        if getattr(message, type):
            return type
    return None


def fill_event(message=None, file=None, account=None, chat=None, user=None, tzinfo=None):
    event = {}

    if message:
        event.update({
            "message_id": message.id,
            "type_id": _get_message_media_type(message),
            "date": message.date.astimezone(tzinfo) if message.date and tzinfo else message.date,
            "date_utc": message.date,
            "text": message.text,
        })
    if file:
        event.update({
            "file_name": file.name,
            "file_size": file.size,
            "file_ext": file.ext,
            "file_type": file.mime_type,
        })

    if account:
        event.update({
            "account_id": account.id,
        })

    if isinstance(chat, Channel):
        event.update({
            "chat_id": get_chat_id(chat),
            "chat_type": "channel",
            "chat_title": chat.title,
        })
    elif isinstance(chat, Chat):
        event.update({
            "chat_id": get_chat_id(chat),
            "chat_type": "group",
            "chat_title": chat.title,
        })
    elif isinstance(chat, User):
        event.update({
            "chat_id": get_chat_id(chat),
            "chat_login": chat.username,
            "chat_fullname": _concat_optional(chat.first_name, chat.last_name),
        })
    elif chat is not None:
        raise ValueError(f"Unsupported type of chat: {type(chat)}")

    if user:
        event.update({
            "user_id": user.id,
            "user_login": user.username,
            "user_fullname": _concat_optional(user.first_name, user.last_name),
        })

    return event
