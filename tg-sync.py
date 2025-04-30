#!/usr/bin/env python3

import argparse
import asyncio
import logging
import os
import yaml

import pyrogram as pg
from pyrogram.enums import MessageMediaType

import tg_sync.actions
from tg_sync.pipeline import Pipeline
from tg_sync.session import Session, Account

logger = logging.getLogger(__name__)

async def run(params):
    with open(params.config) as file:
        config = yaml.safe_load(file)

    log_config = config.get("logging")
    if log_config:
        logging.basicConfig(**log_config)

    pipeline = Pipeline.from_config(config["pipeline"])

    accounts = []
    for account_dir in params.account:
        with open(f"{account_dir}/account.yaml") as file:
            account_data = yaml.safe_load(file)
            accounts.append(Account(workdir=account_dir, **account_data))

    sessions = [Session(account, pipeline) for account in accounts]

    try:
        await asyncio.gather(*[session.start() for session in sessions])

        if params.list_types:
            for type in MessageMediaType:
                logger.info("type_id=%s", type.value)
        for session in sessions:
            if params.list_chats:
                await session.list_chats()
            if params.list_users:
                await session.list_users()

        # incrementally process history:
        await asyncio.gather(*[
            session.process_history(params.offset)
            for session in sessions
        ])

        if params.live:
            await pg.idle()
    finally:
        await asyncio.gather(*[session.stop() for session in sessions])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", required=True)
    parser.add_argument("-a", "--account", required=True, action="append", help="Account directory")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--list-chats", action="store_true")
    parser.add_argument("--list-users", action="store_true")
    parser.add_argument("--list-types", action="store_true")
    parser.add_argument("--offset", default="processed",
        help="""Where to start processing of chat history. One of:
        beginning - process chat from the beginning;
        processed - process chat from the last processed message;
        now - don't process chat history;
        or an ISO 8601 formatted date to process from (e.g. 2025-04-29T00:00:00)""")
    params = parser.parse_args()

    asyncio.run(run(params))


if __name__ == "__main__":
    main()
