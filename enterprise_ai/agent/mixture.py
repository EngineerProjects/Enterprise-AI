"""
Mixture of Agents (MoA) — aggregate responses from N independent agents.

Three aggregation strategies:

  synthesize  (default)
    Run all agents in parallel; feed all responses to an aggregator LLM
    that merges the best insights into one coherent answer.

  vote
    Run all agents in parallel; an LLM judge picks the single best response.
    Returns the winning response verbatim.

  best_of
    Run all agents in parallel; an LLM judge scores every response 1–10;
    the highest-scored response is returned verbatim.

Usage::

    from enterprise_ai.agent.mixture import MixtureOfAgents, AggregationStrategy

    agents = [
        Agent(provider=AnthropicProvider(model="claude-opus-4-8"), ...),
        Agent(provider=OpenAIProvider(model="gpt-4o"), ...),
        Agent(provider=AnthropicProvider(model="claude-haiku-4-5-20251001"), ...),
    ]
    moa = MixtureOfAgents(agents, strategy=AggregationStrategy.synthesize)
    result = await moa.run("Explain the CAP theorem concisely.")
    print(result.output)
    print(f"Strategy: {result.strategy}, winner_index: {result.winner_index}")
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.schema.session import SessionResult


class AggregationStrategy(str, Enum):
    synthesize = "synthesize"  # aggregator LLM merges all answers
    vote = "vote"              # LLM judge picks the best answer
    best_of = "best_of"        # LLM judge scores each; highest wins


@dataclass
class MixtureResult:
    """Result returned by :meth:`MixtureOfAgents.run`."""

    output: str
    strategy: AggregationStrategy
    agent_results: list["SessionResult"]
    winner_index: int | None = None   # set for vote / best_of strategies
    metadata: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------
# Aggregation prompts
# ------------------------------------------------------------------

_SYNTHESIZE_SYSTEM = """\
You are a synthesis assistant.
You will receive multiple agent responses to the same question.
Combine the best insights from each into one coherent, accurate, and complete answer.
Do not mention that you are synthesizing; just give the best possible answer directly.
"""

_VOTE_SYSTEM = """\
You are an impartial judge.
You will receive several agent responses to the same question.
Pick the single best response — the most accurate, complete, and helpful.
Respond with ONLY a JSON object (no extra text): {"winner": <index>}
where <index> is the 0-based integer index of the best response.
"""

_BEST_OF_SYSTEM = """\
You are a quality evaluator.
Score each of the following agent responses on a scale of 1 to 10.
Consider accuracy, completeness, and clarity.
Respond with ONLY a JSON object (no extra text): {"scores": [<score_0>, <score_1>, ...]}
Each score must be a number between 1 and 10.
"""


class MixtureOfAgents:
    """
    Run N agents in parallel and aggregate their responses.

    Args:
        agents:      The agents to run. Must have at least one.
        aggregator:  Agent whose *provider* is used for the aggregation LLM call.
                     Defaults to ``agents[0]``.
        strategy:    How to aggregate.  Default: ``synthesize``.
        timeout:     Optional wall-clock timeout (seconds) for the parallel phase.
                     Agents that time out are replaced with error results.
    """

    def __init__(
        self,
        agents: list["Agent"],
        aggregator: "Agent | None" = None,
        strategy: AggregationStrategy = AggregationStrategy.synthesize,
        timeout: float | None = None,
    ) -> None:
        if not agents:
            raise ValueError("MixtureOfAgents requires at least one agent.")
        self._agents = agents
        self._aggregator = aggregator or agents[0]
        self._strategy = strategy
        self._timeout = timeout

    async def run(
        self,
        prompt: str,
        session_id: str = "",
    ) -> MixtureResult:
        """Run all agents in parallel, then aggregate their responses."""
        agent_results = await self._run_parallel(prompt, session_id)

        if self._strategy == AggregationStrategy.synthesize:
            return await self._synthesize(prompt, agent_results)
        elif self._strategy == AggregationStrategy.vote:
            return await self._vote(prompt, agent_results)
        else:
            return await self._best_of(agent_results)

    # ------------------------------------------------------------------
    # Parallel execution
    # ------------------------------------------------------------------

    async def _run_parallel(
        self,
        prompt: str,
        session_id: str,
    ) -> list["SessionResult"]:
        coros = [
            agent.run(
                prompt,
                session_id=f"{session_id}-{i}" if session_id else "",
            )
            for i, agent in enumerate(self._agents)
        ]
        if self._timeout is not None:
            raw = await asyncio.wait_for(
                asyncio.gather(*coros, return_exceptions=True),
                self._timeout,
            )
        else:
            raw = await asyncio.gather(*coros, return_exceptions=True)

        from enterprise_ai.schema.session import SessionResult, SessionState

        results: list[SessionResult] = []
        for i, r in enumerate(raw):
            if isinstance(r, Exception):
                results.append(
                    SessionResult(
                        session_id=f"agent-{i}-error",
                        output=f"ERROR: {r}",
                        state=SessionState.error,
                    )
                )
            else:
                results.append(r)  # type: ignore[arg-type]
        return results

    # ------------------------------------------------------------------
    # Aggregation strategies
    # ------------------------------------------------------------------

    async def _synthesize(
        self,
        prompt: str,
        results: list["SessionResult"],
    ) -> MixtureResult:
        from enterprise_ai.schema import Message

        responses_block = self._format_responses(results)
        synthesis_prompt = (
            f"Original question: {prompt}\n\n"
            f"Agent responses:\n{responses_block}\n\n"
            "Provide the best synthesized answer:"
        )
        resp = await self._aggregator._provider.complete(
            [Message.system(_SYNTHESIZE_SYSTEM), Message.user(synthesis_prompt)],
            max_tokens=4096,
        )
        return MixtureResult(
            output=resp.content,
            strategy=self._strategy,
            agent_results=results,
        )

    async def _vote(
        self,
        prompt: str,
        results: list["SessionResult"],
    ) -> MixtureResult:
        from enterprise_ai.schema import Message

        responses_block = self._format_responses(results)
        vote_prompt = (
            f"Original question: {prompt}\n\n"
            f"Responses:\n{responses_block}"
        )
        resp = await self._aggregator._provider.complete(
            [Message.system(_VOTE_SYSTEM), Message.user(vote_prompt)],
            max_tokens=128,
        )
        winner = self._parse_winner(resp.content, len(results))
        return MixtureResult(
            output=results[winner].output,
            strategy=self._strategy,
            agent_results=results,
            winner_index=winner,
        )

    async def _best_of(
        self,
        results: list["SessionResult"],
    ) -> MixtureResult:
        from enterprise_ai.schema import Message

        scores_prompt = self._format_responses(results)
        resp = await self._aggregator._provider.complete(
            [Message.system(_BEST_OF_SYSTEM), Message.user(scores_prompt)],
            max_tokens=256,
        )
        winner = self._parse_best_of(resp.content, len(results))
        return MixtureResult(
            output=results[winner].output,
            strategy=self._strategy,
            agent_results=results,
            winner_index=winner,
            metadata={"raw_scores": resp.content},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_responses(results: list["SessionResult"]) -> str:
        lines: list[str] = []
        for i, r in enumerate(results):
            lines.append(f"[Response {i}]:\n{r.output[:1500]}")
        return "\n\n".join(lines)

    @staticmethod
    def _parse_winner(text: str, n: int) -> int:
        cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
        try:
            data = json.loads(cleaned)
            idx = int(data["winner"])
            return max(0, min(idx, n - 1))
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return 0

    @staticmethod
    def _parse_best_of(text: str, n: int) -> int:
        cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
        try:
            data = json.loads(cleaned)
            scores = [float(s) for s in data.get("scores", [])][:n]
            if not scores:
                return 0
            return max(range(len(scores)), key=lambda i: scores[i])
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return 0
