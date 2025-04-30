import logging

from .pipeline import Action, register_action, ExecuteResult
from .event import EVENT_FIELDS

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

    def execute(self, event, **kwargs):
        event.update(self.values)


@register_action
class ExitAction(Action):
    name = "exit"

    def execute(self, event, **kwargs):
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

    def execute(self, event, dry_run=False, **kwargs):
        if dry_run:
            return ExecuteResult.DRY_RUN
        self.logger.log(self.level, self.message.format(event=event))


async def process_message(client, message, env):
        save_path = env["save_path"].format(**env)
        os.makedirs(save_path, exist_ok=True)
        download_path = await client.download_media(message)
        dst_path = get_dst_file(download_path, save_path)
        os.rename(download_path, dst_path)
        logger.info("Saved file %s", dst_path)


