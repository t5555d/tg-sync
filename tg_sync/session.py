import logging

from dataclasses import dataclass

import pyrogram as pg
from pyrogram.enums import MessageMediaType

from .pipeline import Pipeline


logger = logging.getLogger(__name__)


@dataclass
class Account:
    id: str
    api_id: int
    api_hash: str
    phone: str
    workdir: str

    def __repr__(self):
        return f"Account {self.id}"


def create_message_event(account, message):
    media_types = {
        MessageMediaType.AUDIO: "audio",
        MessageMediaType.DOCUMENT: "document",
        MessageMediaType.PHOTO: "photo",
        MessageMediaType.VIDEO: "video",
        MessageMediaType.VOICE: "voice",
    }
    media_type = getattr(message, "media", None)
    media_type = media_types.get(media_type)

    return {
        "message_id": message.id,
        "date": message.date,
        "account_id": account.id,
        "chat_id": getattr(message.chat, "id", None),
        "user_id": getattr(message.from_user, "id", None),
        "type_id": media_type,
    }


class Session:
    def __init__(self, account: Account, pipeline: Pipeline):
        self.account = account
        self.pipeline = pipeline
        self.client = pg.Client(
            account.id,
            account.api_id,
            account.api_hash,
            phone_number=account.phone,
            workdir=account.workdir,
        )

        msg_handler = pg.handlers.MessageHandler(self.on_message)
        self.client.add_handler(msg_handler)

    async def start(self):
        logger.info("%s: starting...", self.account)
        await self.client.start()

    async def stop(self):
        logger.info("%s: stopping...", self.account)
        await self.client.stop()

    async def list_chats(self):
        logger.info("%s: listing available chats", self.account)
        async for dialog in self.client.get_dialogs():
            chat = dialog.chat
            logger.info("Chat %d: %s", chat.id, repr(chat))

    async def on_message(self, client, message):
        event = create_message_event(self.account, message)
        self.pipeline.execute(event)


