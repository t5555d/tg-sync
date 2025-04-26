import logging

from .pipeline import Action


logger = logging.getLogger(__name__)


def set_values(event, params):
    event.update(params)

def get_log_level_variants(level):
    yield level
    yield logging.getLevelName(level)
    yield logging.getLevelName(level.upper())

def get_log_level(level):
    for variant in get_log_level_variants(level):
        if isinstance(variant, int):
            return variant

def log_values(event, params):
    level = params.get("level", "INFO")
    level = get_log_level(level)
    message = params.get("message", "Event: {event}")
    logger.log(level, message.format(event=event))

Action.register_executer("set", set_values)
Action.register_executer("log", log_values)


async def process_message(client, message, env):
    action = env.get("action")
    if action == "debug":
        logger.debug("Action %s, Env %s, Message %s", action, env, message)
    if action == "log":
        logger.info("Action %s, Env %s", action, env)

    if action == "save":
        save_path = env["save_path"].format(**env)
        os.makedirs(save_path, exist_ok=True)
        download_path = await client.download_media(message)
        dst_path = get_dst_file(download_path, save_path)
        os.rename(download_path, dst_path)
        logger.info("Saved file %s", dst_path)


