import logging

from enum import Enum, auto
from typing import Optional

from .event import EVENT_FIELDS


logger = logging.getLogger(__name__)


class Filter:
    MATCH_POSSIBLE = "---tg-sync-match-possible---"

    def __init__(self, **values):
        self.values = values

    def __repr__(self):
        return f"Filter: {self.values}"

    def matches_key(self, event, key) -> bool:
        if event.get(key) == Filter.MATCH_POSSIBLE:
            return None
        actual_value = event.get(key)
        expected_value = self.values.get(key)
        if isinstance(expected_value, list):
            return actual_value in expected_value
        else:
            return actual_value == expected_value

    def matches(self, event: dict) -> bool:
        filter_result = True
        for key in self.values:
            key_result = self.matches_key(event, key)
            if key_result is False:
                return False
            if key_result is None:
                filter_result = None
        return filter_result


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
        try:
            return Action.subclasses[action](**params)
        except Exception as err:
            raise ValueError(f"Failed to create action '{action}' from {params}") from err

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

    async def filter_step(self, event: dict) -> "ProcessingStep":
        filter_result = True
        possibly_matching_filters = []
        if self.filters:
            filter_results = [(filter, filter.matches(event)) for filter in self.filters]
            possibly_matching_filters = [
                filter for filter, result in filter_results if result is not False
            ]
            if not possibly_matching_filters:
                return None
            if any(result is None for filter, result in filter_results):
                filter_result = None
        executed_actions = []
        has_modify = False
        has_exit = False
        for action in self.actions:
            result = await action.execute(event, dry_run=True)
            if result == ExecuteResult.EXIT_STEP:
                break
            if result == ExecuteResult.DRY_RUN:
                has_modify = True
            if result == ExecuteResult.EXIT_PIPELINE and filter_result is True:
                has_exit = True
                break
            executed_actions.append(action)
        return possibly_matching_filters, executed_actions, has_modify, has_exit


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

    async def filter_pipeline(self, sample_event) -> Optional["Pipeline"]:
        event = {
            key : Filter.MATCH_POSSIBLE
            for key in EVENT_FIELDS
        }
        event.update(sample_event)
        filtered_steps = []
        has_meaningful_actions = False
        for step in self.steps:
            step_data = await step.filter_step(event)
            if step_data is None:
                continue  # filters not passing, skip
            filters, actions, has_modify, has_exit = step_data

            has_meaningful_actions |= has_modify
            filtered_steps.append(ProcessingStep(filters, actions))

            if has_exit:
                break

        if has_meaningful_actions:
            return Pipeline(filtered_steps)
        else:
            return None
