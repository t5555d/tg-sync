import logging

from dataclasses import dataclass

import pyrogram as pg

from .event import fill_event
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
            chat_event = fill_event(chat=dialog.chat)
            logger.info("Chat %s", repr(chat_event))
            pipeline = self.pipeline.filter_pipeline(account=self.account, chat=dialog.chat)
            if pipeline:
                logger.info(repr(pipeline))

    async def list_users(self):
        logger.info("%s: listing available users")
        for user in await self.client.get_contacts():
            user_event = fill_event(user=user)
            logger.info("User %s", repr(user_event))

    async def on_message(self, client, message):
        event = fill_event(
            message=message,
            account=self.account,
            chat=message.chat,
            user=message.from_user,
        )
        self.pipeline.execute(event)


