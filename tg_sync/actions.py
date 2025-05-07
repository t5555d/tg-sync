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

    def __init__(self, logger=None, level="INFO", message="Event: {event}"):
        def get_log_level_variants(level):
            yield level
            yield logging.getLevelName(level)
            yield logging.getLevelName(level.upper())

        self.logger = logging.getLogger(logger or f"{__name__}.{self.name}")
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

    def __init__(self, save_path: str, old_save_path: str = None, skip_existing: bool = False):
        self.save_path = save_path
        self.old_save_path = old_save_path
        self.skip_existing = skip_existing
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    async def execute(self, event, dry_run=False, **kwargs):
        if dry_run:
            return ExecuteResult.DRY_RUN
        save_path = self.save_path.format(**event)
        if self.skip_existing:
            if os.path.exists(save_path) and os.path.getsize(save_path) == event["file_size"]:
                self.logger.info("Skip downloading existing file %s", save_path)
                return ExecuteResult.SKIPPED

            if self.old_save_path:
                old_save_path = self.old_save_path.format(**event)
                if os.path.exists(old_save_path) and os.path.getsize(old_save_path) == event["file_size"]:
                    os.rename(old_save_path, save_path)
                    self.logger.info("Moved file from old location: %s", save_path)
                    return None

        session = Session.get(event["account_id"])
        download_path = await session.download_media(event["chat_id"], event["message_id"])
        save_dir = os.path.dirname(save_path)
        os.makedirs(save_dir, exist_ok=True)
        uniq_path = get_uniq_path(save_path)
        os.rename(download_path, uniq_path)
        self.logger.info("Saved file %s", uniq_path)
