import aiofiles
import os.path
import yaml

from datetime import datetime

from telethon.types import Channel, Chat, User, PeerChannel, PeerChat, PeerUser
from telethon.utils import get_peer_id

async def save_yaml(data, path):
    async with aiofiles.open(path, "w") as file:
        await file.write(yaml.dump(data))
        await file.flush()

def parse_timezone(tz: str):
    date = datetime.strptime(tz, "%z")
    return date.tzinfo

def get_uniq_path(file_path: str) -> str:
    (base, ext) = os.path.splitext(file_path)
    count = 1
    while os.path.exists(file_path):
        count += 1
        file_path = f"{base} ({count}){ext}"
    return file_path

def get_chat_id(chat):
    if isinstance(chat, Channel):
        return get_peer_id(PeerChannel(chat.id))
    elif isinstance(chat, Chat):
        return get_peer_id(PeerChat(chat.id))
    elif isinstance(chat, User):
        return get_peer_id(PeerUser(chat.id))
    else:
        raise ValueError(f"Unsupported type of chat: {type(chat)}")
