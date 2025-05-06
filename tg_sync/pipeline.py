import logging

from enum import Enum, auto
from typing import Optional

from .event import EVENT_FIELDS, fill_event

logger = logging.getLogger(__name__)


class Filter:
    MATCH_ALWAYS = "---tg-sync-match-always---"

    def __init__(self, **values):
        self.values = values

    def __repr__(self):
        return f"Filter: {self.values}"

    def matches_key(self, event, key) -> bool:
        if event.get(key) == Filter.MATCH_ALWAYS:
            return True
        actual_value = event.get(key)
        expected_value = self.values.get(key)
        if isinstance(expected_value, list):
            return actual_value in expected_value
        else:
            return actual_value == expected_value

    def matches(self, event: dict) -> bool:
        return all(
            self.matches_key(event, key)
            for key in self.values
        )


class ExecuteResult(Enum):
    SKIPPED = auto()
    DRY_RUN = auto()
    EXIT_STEP = auto()
    EXIT_PIPELINE = auto()


class Action:
    subclasses = {}

    @staticmethod
    def from_config(action: str, **params):
        if action not in Action.subclasses:
            raise ValueError(f"Unknown action '{action}'")
        return Action.subclasses[action](**params)

    def __repr__(self):
        return f"Action {self.name}"

    async def execute(self, event: dict, **kwargs) -> Optional[ExecuteResult]:
        raise RuntimeError("Action.execute should be implemented")


def register_action(action_class):
    action_name = action_class.name
    registered_class = Action.subclasses.get(action_name)
    if registered_class:
        raise ValueError(f"Action '{action_name}' is registered multiple times: {registered_class} and {action_class}")
    Action.subclasses[action_name] = action_class


class ProcessingStep:
    @staticmethod
    def from_config(actions: list[dict], filters: list[dict] = None) -> "ProcessingStep":
        return ProcessingStep(
            filters=[Filter(**filter) for filter in (filters or [])],
            actions=[Action.from_config(**action) for action in actions],
        )

    def __init__(self, filters: list[Filter], actions: list[Action]):
        self.filters = filters
        self.actions = actions

    def __repr__(self):
        return ", ".join(repr(item) for item in self.filters + self.actions)

    async def execute(self, event: dict, **kwargs) -> Optional[ExecuteResult]:
        if self.filters and all(not filter.matches(event) for filter in self.filters):
            return ExecuteResult.SKIPPED
        for action in self.actions:
            result = await action.execute(event, **kwargs)
            if result == ExecuteResult.EXIT_STEP:
                break
            if result in (ExecuteResult.EXIT_PIPELINE, ExecuteResult.DRY_RUN):
                return result


class Pipeline:

    @staticmethod
    def from_config(steps: list[dict]) -> "Pipeline":
        return Pipeline([ProcessingStep.from_config(**step) for step in steps])

    def __init__(self, steps: list[ProcessingStep]):
        self.steps = steps

    def __repr__(self):
        return f"Pipeline:\n- " + "\n- ".join(repr(step) for step in self.steps)

    async def execute(self, event: dict):
        logger.debug("Got event %s", event)
        for step in self.steps:
            result = await step.execute(event)
            logger.debug("Got result %s from step %s", result, step)
            if result == ExecuteResult.EXIT_PIPELINE:
                break

    async def filter_pipeline(self, **kwargs) -> Optional["Pipeline"]:
        event = {
            key : Filter.MATCH_ALWAYS
            for key in EVENT_FIELDS
        }
        fill_event(event, **kwargs)
        filtered_steps = []
        has_meaningful_actions = False
        for step in self.steps:
            result = await step.execute(event, dry_run=True)
            if result == ExecuteResult.SKIPPED:
                continue  # filters not passing, skip
            if result == ExecuteResult.EXIT_PIPELINE:
                break
            if result == ExecuteResult.DRY_RUN:
                has_meaningful_actions = True
            filtered_steps.append(step)

        if has_meaningful_actions:
            return Pipeline(filtered_steps)
        else:
            return None
