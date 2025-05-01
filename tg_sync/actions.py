import logging
import os

from .event import EVENT_FIELDS
from .pipeline import Action, register_action, ExecuteResult
from .session import Session
from .utils import get_uniq_path

logger = logging.getLogger(__name__)


@register_action
class SetAction(Action):
    name = "set"

    def __init__(self, **values):
        for key in values:
            if key in EVENT_FIELDS:
                raise ValueError(f"Action '{self.name}' can't override built-in key: '{key}'")
        self.values = values

    def __repr__(self):
        return f"Action {self.name}: " + ", ".join(f"{key}={val}" for key, val in self.values.items())

    async def execute(self, event, **kwargs):
        event.update(self.values)


@register_action
class ExitAction(Action):
    name = "exit"

    async def execute(self, event, **kwargs):
        return ExecuteResult.EXIT_PIPELINE


@register_action
class LogAction(Action):
    name = "log"

    def __init__(self, logger="tg-sync", level="INFO", message="Event: {event}"):
        def get_log_level_variants(level):
            yield level
            yield logging.getLevelName(level)
            yield logging.getLevelName(level.upper())

        self.logger = logging.getLogger()
        self.level = next(lvl for lvl in get_log_level_variants(level) if isinstance(lvl, int))
        self.message = message

    def __repr__(self):
        return f"Action '{self.name}': level={self.level}"

    async def execute(self, event, dry_run=False, **kwargs):
        if dry_run:
            return ExecuteResult.DRY_RUN
        self.logger.log(self.level, self.message.format(event=event))


@register_action
class SaveAction(Action):
    name = "save"

    def __init__(self, save_path: str):
        self.save_path = save_path

    async def execute(self, event, dry_run=False, **kwargs):
        if dry_run:
            return ExecuteResult.DRY_RUN
        session = Session.get(event["account_id"])
        download_path = await session.download_media(event["chat_id"], event["message_id"])
        file_name = os.path.basename(download_path)
        (base, ext) = os.path.splitext(file_name)
        save_path = self.save_path.format(file_name=file_name, base_name=base, ext=ext, **event)
        save_dir = os.path.dirname(save_path)
        os.makedirs(save_dir, exist_ok=True)
        uniq_path = get_uniq_path(save_path)
        os.rename(download_path, uniq_path)
        logger.info("Saved file %s", uniq_path)
