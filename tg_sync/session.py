import logging
import os.path
import yaml

from dataclasses import dataclass
from datetime import datetime

import pyrogram as pg

from .event import fill_event
from .pipeline import Pipeline
from .utils import save_yaml


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
    instances: dict[str, "Session"] = {}

    @staticmethod
    def get(account_id: str) -> "Session":
        return Session.instances[account_id]

    def __init__(self, account: Account, pipeline: Pipeline):
        self.account = account
        self.pipeline = pipeline
        self.chat_pipelines = {}
        self.client = pg.Client(
            account.id,
            account.api_id,
            account.api_hash,
            phone_number=account.phone,
            workdir=account.workdir,
        )
        self.progress = {}
        self.progress_path = account.workdir + "/progress.yaml"
        if os.path.exists(self.progress_path):
            with open(self.progress_path) as file:
                self.progress = yaml.safe_load(file)
        if not self.progress:
            self.progress = {}

        Session.instances[account.id] = self

    async def _get_chat_pipeline(self, chat):
        if chat.id in self.chat_pipelines:
            return self.chat_pipelines[chat.id]
        chat_pipeline = await self.pipeline.filter_pipeline(account=self.account, chat=chat)
        self.chat_pipelines[chat.id] = chat_pipeline
        return chat_pipeline

    async def _process_message(self, message, pipeline):
        event = fill_event(
            message=message,
            account=self.account,
            chat=message.chat,
            user=message.from_user,
        )
        await pipeline.execute(event)
        await self._message_processed(message)

    async def _message_processed(self, message):
        self.progress[message.chat.id] = message.id
        await save_yaml(self.progress, self.progress_path)

    async def _get_chat_history(self, chat_id, limit, **offsets):
        messages = []
        batch_options = dict(limit=limit, offset=-limit)
        async for message in self.client.get_chat_history(chat_id, **offsets, **batch_options):
            # messages are yielded in reverse chronological order
            # if we detect first message again, then there are no any messages
            if messages and messages[0].id == message.id:
                break
            if message.id == offsets.get("offset_id"):
                break
            messages.append(message)
        messages.reverse()
        return messages

    async def _process_history(self, offset: str):
        async for dialog in self.client.get_dialogs():
            chat_pipeline = await self._get_chat_pipeline(dialog.chat)
            if not chat_pipeline:
                continue

            chat_id = dialog.chat.id
            offsets = {}
            if offset == "processed":
                offsets["offset_id"] = self.progress.get(chat_id, 0)
            elif offset == "beginning":
                offsets["offset_id"] = 0
            else:
                offsets["offset_date"] = datetime.fromisoformat(offset)

            batch_size = 30
            messages = await self._get_chat_history(chat_id, batch_size, **offsets)
            while messages:
                for message in messages:
                    await self._process_message(message, chat_pipeline)
                messages = await self._get_chat_history(chat_id, batch_size, offset_id=self.progress[chat_id])

    async def start(self, offset: str, live: bool):
        logger.info("%s: starting...", self.account)
        await self.client.start()

        if offset != "now":
            await self._process_history(offset)
        if live:
            msg_handler = pg.handlers.MessageHandler(self._on_message)
            self.client.add_handler(msg_handler)

    async def stop(self):
        logger.info("%s: stopping...", self.account)
        await self.client.stop()

    async def list_chats(self):
        logger.info("%s: listing available chats", self.account)
        async for dialog in self.client.get_dialogs():
            chat_event = fill_event(chat=dialog.chat)
            logger.info("Chat %s", repr(chat_event))
            chat_pipeline = await self._get_chat_pipeline(dialog.chat)
            if chat_pipeline:
                logger.info(repr(chat_pipeline))

    async def list_users(self):
        logger.info("%s: listing available users")
        for user in await self.client.get_contacts():
            user_event = fill_event(user=user)
            logger.info("User %s", repr(user_event))

    async def _on_message(self, client, message):
        chat_pipeline = await self._get_chat_pipeline(message.chat)
        if chat_pipeline:
            await self._process_message(message, chat_pipeline)

    async def download_media(self, chat_id: int, message_id: int):
        message = await self.client.get_messages(chat_id, message_id)
        download_path = await self.client.download_media(message)
        return download_path
