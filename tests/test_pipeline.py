import pytest

import tg_sync.actions
from tg_sync.pipeline import Pipeline, Filter, Action

pytest_plugins = ('pytest_asyncio',)

@pytest.mark.asyncio
async def test_simple_pipeline():
    pipeline = Pipeline.from_config([
        {
            "filters": [
                { "chat_id": 123, "type_id": "photo" },
                { "chat_id": 456, "type_id": ["photo", "video"] },
            ],
            "actions": [
                { "action": "set", "save_media": True },
            ]
        },
        {
            "filters": [
                { "save_media": True },
            ],
            "actions": [
                { "action": "save", "save_path": "{file_name}" },
            ]
        }
    ])

    assert repr(await pipeline.filter_pipeline({
        "chat_id": 123,
    })) == """Pipeline:
- Filter: {'chat_id': 123, 'type_id': 'photo'}, Action set: save_media=True
- Filter: {'save_media': True}, Action save"""

    assert repr(await pipeline.filter_pipeline({
        "chat_id": 456,
    })) == """Pipeline:
- Filter: {'chat_id': 456, 'type_id': ['photo', 'video']}, Action set: save_media=True
- Filter: {'save_media': True}, Action save"""

    assert await pipeline.filter_pipeline({
        "chat_id": 789,
    }) is None


@pytest.mark.asyncio
async def test_exit_pipeline():
    pipeline = Pipeline.from_config([
        {
            "filters": [
                { "chat_id": 123 },
                { "chat_id": 456, "type_id": "photo" },
            ],
            "actions": [
                { "action": "exit" },
            ]
        },
        {
            "actions": [
                { "action": "log" },
            ]
        }
    ])

    assert await pipeline.filter_pipeline({
        "chat_id": 123,
    }) is None

    assert repr(await pipeline.filter_pipeline({
        "chat_id": 456,
    })) == \
"""Pipeline:
- Filter: {'chat_id': 456, 'type_id': 'photo'}, Action exit
- Action log: level=20"""

    assert repr(await pipeline.filter_pipeline({
        "chat_id": 789,
    })) == \
"""Pipeline:
- Action log: level=20"""


