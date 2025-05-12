from telethon.types import Channel, Chat, User
from telethon.utils import get_input_location

from .utils import get_chat_id


class ChatField:
    CHAT_ID = "chat_id"
    CHAT_TYPE = "chat_type"
    CHAT_TITLE = "chat_title"
    CHAT_LOGIN = "chat_login"


class UserField:
    USER_ID = "user_id"
    USER_LOGIN = "user_login"
    USER_TITLE = "user_title"


class FileField:
    FILE_EXT = "file_ext"
    FILE_NAME = "file_name"
    FILE_SIZE = "file_size"
    FILE_TYPE = "file_type"


class EventField(ChatField, UserField):
    ACCOUNT_ID = "account_id"
    MESSAGE_ID = "message_id"
    TYPE_ID = "type_id"
    TEXT = "text"
    DATE = "date"
    DATE_UTC = "date_utc"
    FORWARD = "forward"


def _get_fields(cls):
    return frozenset({
        value for key, value in cls.__dict__.items()
        if not key.startswith("__")
    })


def _add_prefix(fields, prefix):
    return { prefix + field for field in fields }


FORWARD_PREFIX = "forward_"

ChatField.ALL = _get_fields(ChatField)
UserField.ALL = _get_fields(UserField)
FileField.ALL = _get_fields(FileField)


EVENT_FIELDS = frozenset(
    ChatField.ALL |
    UserField.ALL |
    FileField.ALL |
    _add_prefix(ChatField.ALL, FORWARD_PREFIX) |
    _add_prefix(UserField.ALL, FORWARD_PREFIX) |
    _get_fields(EventField)
)

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


def fill_event(message=None, file=None, account=None, chat=None, user=None, fwd_chat=None, fwd_user=None, tzinfo=None):
    event = {}

    if message:
        event.update({
            EventField.MESSAGE_ID: message.id,
            EventField.TYPE_ID: _get_message_media_type(message),
            EventField.DATE: message.date.astimezone(tzinfo) if message.date and tzinfo else message.date,
            EventField.DATE_UTC: message.date,
            EventField.TEXT: message.text,
            EventField.FORWARD: fwd_chat is not None or fwd_user is not None,
        })
    if file:
        event.update({
            FileField.FILE_EXT: file.ext,
            FileField.FILE_NAME: file.name,
            FileField.FILE_SIZE: file.size,
            FileField.FILE_TYPE: file.mime_type,
        })

    if account:
        event.update({
            EventField.ACCOUNT_ID: account.id,
        })

    if isinstance(chat, Channel):
        event.update({
            ChatField.CHAT_ID: get_chat_id(chat),
            ChatField.CHAT_TYPE: "channel",
            ChatField.CHAT_TITLE: chat.title,
        })
    elif isinstance(chat, Chat):
        event.update({
            ChatField.CHAT_ID: get_chat_id(chat),
            ChatField.CHAT_TYPE: "group",
            ChatField.CHAT_TITLE: chat.title,
        })
    elif isinstance(chat, User):
        event.update({
            ChatField.CHAT_ID: get_chat_id(chat),
            ChatField.CHAT_TYPE: "private",
            ChatField.CHAT_TITLE: _concat_optional(chat.first_name, chat.last_name),
            ChatField.CHAT_LOGIN: chat.username,
        })
    elif chat is not None:
        raise ValueError(f"Unsupported type of chat: {type(chat)}")

    if user:
        event.update({
            UserField.USER_ID: user.id,
            UserField.USER_LOGIN: user.username,
            UserField.USER_TITLE: _concat_optional(user.first_name, user.last_name),
        })

    if fwd_chat or fwd_user:
        fwd_event = fill_event(chat=fwd_chat, user=fwd_user)
        for key, value in fwd_event.items():
            event[FORWARD_PREFIX + key] = value

    return event
