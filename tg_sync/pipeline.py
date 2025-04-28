import logging

from dataclasses import dataclass
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

    def matches_partially(self, **kwargs) -> bool:
        return all(
            key not in event or self.matches_key(event, key)
            for key in self.values
        )


class ExecuteResult(Enum):
    SKIPPED = auto()
    DRY_RUN = auto()
    EXIT_STEP = auto()
    EXIT_PIPELINE = auto()


class Action:
    executers = {}

    @staticmethod
    def register_executer(action: str, executer):
        Action.executers[action] = executer

    @staticmethod
    def get_executer(action: str):
        if action not in Action.executers:
            raise ValueError(f"Unknown action '{action}'")
        return Action.executers[action]

    def __init__(self, action: str, **params):
        self.action = action
        self.params = params
        self.executer = Action.get_executer(action)

    def __repr__(self):
        return f"Action {self.action}({self.params})"

    def execute(self, event: dict, **kwargs) -> Optional[ExecuteResult]:
        return self.executer(event, self.params, **kwargs)


@dataclass
class ProcessingStep:
    filters: Optional[list[Filter]]
    actions: list[Action]

    def __post_init__(self):
        self.filters = [Filter(**filter) for filter in self.filters]
        self.actions = [Action(**action) for action in self.actions]

    def matches_partially(self, **kwargs):
        return any(
            filter.matches_partially(**kwargs)
            for filter in self.filters
        )

    def execute(self, event: dict, **kwargs) -> Optional[ExecuteResult]:
        if self.filters and all(not filter.matches(event) for filter in self.filters):
            return ExecuteResult.SKIPPED
        for action in self.actions:
            result = action.execute(event, **kwargs)
            if result == ExecuteResult.EXIT_STEP:
                break
            if result in (ExecuteResult.EXIT_PIPELINE, ExecuteResult.DRY_RUN):
                return result


class Pipeline:

    @staticmethod
    def from_config(steps: list[dict]) -> "Pipeline":
        return Pipeline([ProcessingStep(**step) for step in steps])

    def __init__(self, steps: list[ProcessingStep]):
        self.steps = steps

    def __repr__(self):
        return f"Pipeline:\n- " + "\n- ".join(repr(step) for step in self.steps)

    def execute(self, event: dict):
        logger.debug("Got event %s", event)
        for step in self.steps:
            result = step.execute(event)
            logger.debug("Got result %s from step %s", result, step)
            if result == ExecuteResult.EXIT_PIPELINE:
                break

    def filter_pipeline(self, **kwargs) -> Optional["Pipeline"]:
        event = {
            key : Filter.MATCH_ALWAYS
            for key in EVENT_FIELDS
        }
        fill_event(event, **kwargs)
        filtered_steps = []
        has_meaningful_actions = False
        for step in self.steps:
            result = step.execute(event, dry_run=True)
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
