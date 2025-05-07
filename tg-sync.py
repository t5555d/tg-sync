#!/usr/bin/env python3

import argparse
import asyncio
import logging
import logging.config
import os
import yaml

import tg_sync.actions
from tg_sync.event import MEDIA_TYPES
from tg_sync.pipeline import Pipeline
from tg_sync.session import Session, Account

logger = logging.getLogger("tg_sync")

async def run(params):
    with open(params.config) as file:
        config = yaml.safe_load(file)

    log_config = config.get("logging")
    if log_config:
        logging.config.dictConfig(log_config)

    pipeline = Pipeline.from_config(config["pipeline"])

    accounts = []
    for account_dir in params.account:
        with open(f"{account_dir}/account.yaml") as file:
            account_data = yaml.safe_load(file)
            accounts.append(Account(workdir=account_dir, **account_data))

    sessions = [Session(account, pipeline) for account in accounts]

    try:
        await asyncio.gather(*[
            session.start(offset=params.offset, live=params.live)
            for session in sessions
        ])

        if params.list_types:
            for type in MEDIA_TYPES:
                logger.info("type_id=%s", type)
        for session in sessions:
            if params.list_chats:
                await session.list_chats()
            if params.list_users:
                await session.list_users()

        if params.live:
            await asyncio.Event().wait()
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

    # do no actions on config keys
    if params.list_chats or params.list_users or params.list_types:
        params.offset = "now"
        params.live = False

    asyncio.run(run(params))


if __name__ == "__main__":
    main()
