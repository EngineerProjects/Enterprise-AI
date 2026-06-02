from __future__ import annotations

from enum import Enum


class ExecutionMode(str, Enum):
    """
    Controls how the agent executes tool calls.

    execute         — default; tools are executed normally
    plan            — tools are described but not executed; the agent
                      produces a plan of what it would do
    pair_programming — collaborative mode; same as execute but signals
                      to the caller that interactive feedback is expected
    """

    execute = "execute"
    plan = "plan"
    pair_programming = "pair_programming"


def is_plan_mode(mode: ExecutionMode | str) -> bool:
    return ExecutionMode(mode) == ExecutionMode.plan


def is_execute_mode(mode: ExecutionMode | str) -> bool:
    m = ExecutionMode(mode)
    return m in (ExecutionMode.execute, ExecutionMode.pair_programming)


def is_pair_programming_mode(mode: ExecutionMode | str) -> bool:
    return ExecutionMode(mode) == ExecutionMode.pair_programming
