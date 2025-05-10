import asyncio
import logging
import os
import os.path
import yaml

from dataclasses import dataclass
from datetime import datetime

import telethon as tt

from .event import fill_event
from .pipeline import Pipeline
from .utils import get_chat_id, parse_timezone, save_yaml


logger = logging.getLogger(__name__)


@dataclass
class Account:
    id: str
    api_id: int
    api_hash: str
    workdir: str
    phone: str = None
    password: str = None
    bot_token: str = None
    timezone: str = None

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
        self.client = tt.TelegramClient(
            f"{account.workdir}/{account.id}.session",
            account.api_id,
            account.api_hash,
            sequential_updates=True,
        )
        self.progress = {}
        self.progress_path = f"{account.workdir}/progress.yaml"
        if os.path.exists(self.progress_path):
            with open(self.progress_path) as file:
                self.progress = yaml.safe_load(file)
        if not self.progress:
            self.progress = {}

        self.tzinfo = None
        if account.timezone:
            self.tzinfo = parse_timezone(account.timezone)

        Session.instances[account.id] = self

    async def _get_chat_pipeline(self, chat):
        chat_id = get_chat_id(chat)
        if chat_id in self.chat_pipelines:
            return self.chat_pipelines[chat_id]
        sample_event = fill_event(account=self.account, chat=chat)
        chat_pipeline = await self.pipeline.filter_pipeline(sample_event)
        self.chat_pipelines[chat_id] = chat_pipeline
        return chat_pipeline

    async def _get_chat_and_pipeline(self, chat_id):
        if chat_id in self.chat_pipelines:
            pipeline = self.chat_pipelines[chat_id]
            chat = pipeline and await self.client.get_entity(chat_id)
            return chat, pipeline
        else:
            chat = await self.client.get_entity(chat_id)
            pipeline = self._get_chat_pipeline(chat)
            return chat, pipeline

    async def _process_message(self, message, chat, pipeline):
        event = fill_event(
            message=message,
            file=message.file,
            account=self.account,
            chat=chat,
            user=await message.get_sender(),
            tzinfo=self.tzinfo,
        )
        await pipeline.execute(event)
        self.progress[event["chat_id"]] = message.id
        await save_yaml(self.progress, self.progress_path)

    async def _process_chat_history(self, chat, offset: str, pipeline: Pipeline):
        offset_id = 0
        offset_date = None
        if offset is None:
            chat_id = get_chat_id(chat)
            offset_id = self.progress.get(chat_id, 0)
        elif offset != "beginning":
            offset_date = datetime.fromisoformat(offset)

        async for message in self.client.iter_messages(chat, offset_id=offset_id, offset_date=offset_date, reverse=True):
            await self._process_message(message, chat, pipeline)

    async def _process_history(self, offset: str):
        tasks = []
        async for dialog in self.client.iter_dialogs():
            chat_pipeline = await self._get_chat_pipeline(dialog.entity)
            if chat_pipeline:
                tasks.append(self._process_chat_history(dialog.entity, offset, chat_pipeline))
        await asyncio.gather(*tasks)

    async def start(self, offset: str, live: bool):
        logger.info("%s: starting...", self.account)
        await self.client.start(
            phone=self.account.phone,
            password=self.account.password,
            bot_token=self.account.bot_token,
        )

        if offset != "now":
            await self._process_history(offset)
        if live:
            self.client.add_event_handler(self._on_message, tt.events.NewMessage)

    async def stop(self):
        logger.info("%s: stopping...", self.account)
        await self.client.disconnect()

    async def list_chats(self):
        logger.info("%s: listing available chats", self.account)
        async for dialog in self.client.iter_dialogs():
            chat_event = fill_event(chat=dialog.entity)
            logger.info("Chat %s", repr(chat_event))
            logger.debug("%s", dialog.entity.stringify())
            chat_pipeline = await self._get_chat_pipeline(dialog.entity)
            if chat_pipeline:
                logger.info(repr(chat_pipeline))

    async def list_users(self):
        logger.info("%s: listing available users")
        async for dialog in self.client.iter_dialogs():
            entity = dialog.entity
            if isinstance(entity, tt.types.User):
                user_event = fill_event(user=entity)
                logger.info("User %s", repr(user_event))
                logger.debug("%s", dialog.entity.stringify())

    async def _on_message(self, message):
        chat, pipeline = await self._get_chat_and_pipeline(message.chat_id)
        if pipeline:
            await self._process_message(message, chat, pipeline)

    async def download_media(self, chat_id: int, message_id: int):
        message = await self.client.get_messages(chat_id, ids=message_id)
        download_dir = f"{self.account.workdir}/downloads"
        os.makedirs(download_dir, exist_ok=True)
        download_path = f"{download_dir}/{chat_id}-{message_id}.tmp"
        progress = lambda current, total: logger.debug(f"Download media {chat_id}/{message_id}: {current}/{total} bytes ({100 * current // total}%)")
        return await self.client.download_media(message, file=download_path, progress_callback=progress)
