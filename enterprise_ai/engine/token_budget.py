from __future__ import annotations

from dataclasses import dataclass

import enterprise_ai.prompt.templates as _tpl


@dataclass
class TokenBudgetConfig:
    turn_token_budget: int = 0
    budget_completion_threshold: float = 0.90
    budget_diminishing_tokens: int = 500
    budget_continuation_limit: int = 5


@dataclass
class BudgetDecision:
    continue_loop: bool = False
    nudge_message: str = ""


class TokenBudgetTracker:
    def __init__(self, config: TokenBudgetConfig) -> None:
        self._config = config
        self.total_turn_tokens: int = 0
        self.budget_continuation_count: int = 0
        self.last_budget_check_tokens: int = 0
        self.last_budget_delta: int = 0

    def record_tokens(self, input_tokens: int, output_tokens: int) -> None:
        self.total_turn_tokens += input_tokens + output_tokens

    def should_continue_for_budget(self, budget: int, has_tool_calls: bool) -> BudgetDecision:
        if budget <= 0:
            return BudgetDecision()
        if self.budget_continuation_count >= self._config.budget_continuation_limit:
            return BudgetDecision()
        # Agent finished — no nudge needed
        if not has_tool_calls:
            return BudgetDecision()

        # Diminishing returns: two consecutive checks with < budget_diminishing_tokens delta
        current = self.total_turn_tokens
        delta = current - self.last_budget_check_tokens
        if self.last_budget_check_tokens > 0 and delta < self._config.budget_diminishing_tokens:
            return BudgetDecision()

        # Consumed enough of the budget → stop nudging
        if current >= self._config.budget_completion_threshold * budget:
            return BudgetDecision()

        self.last_budget_delta = delta
        self.last_budget_check_tokens = current
        self.budget_continuation_count += 1
        return BudgetDecision(continue_loop=True, nudge_message=_tpl.BUDGET_NUDGE_MESSAGE)

    def reset(self) -> None:
        self.total_turn_tokens = 0
        self.budget_continuation_count = 0
        self.last_budget_check_tokens = 0
        self.last_budget_delta = 0
