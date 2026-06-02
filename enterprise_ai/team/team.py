from __future__ import annotations

import asyncio
import uuid

from enterprise_ai.agent.agent import Agent
from enterprise_ai.schema import SessionResult
from enterprise_ai.team.mailbox import Mailbox
from enterprise_ai.team.task_board import TaskBoard


class TeamResult:
    def __init__(self, outputs: dict[str, str], task_summary: str) -> None:
        self.outputs = outputs          # agent_id → final output
        self.task_summary = task_summary

    @property
    def combined_output(self) -> str:
        return "\n\n---\n\n".join(
            f"[{aid}]\n{out}" for aid, out in self.outputs.items() if out
        )


class Team:
    """
    A team of autonomous agents that collaborate via a shared mailbox and task board.

    Each agent runs as a persistent, parallel session. There is no central
    orchestrator dictating actions — agents communicate via mail and claim
    tasks from a shared board, just like a real organization.

    Usage:
        team = Team(
            agents=[
                Agent(system_prompt="You are the team manager. Decompose missions and post tasks."),
                Agent(system_prompt="You are a developer. Claim development tasks and implement them."),
            ]
        )
        result = await team.run("Implement a REST API for user management")

    The mission is posted to the mailbox as a broadcast. Each agent reads its
    mail, decides what to do next, and acts autonomously.
    """

    def __init__(
        self,
        agents: list[Agent],
        mailbox: Mailbox | None = None,
        task_board: TaskBoard | None = None,
        mission_timeout: float = 300.0,
        max_tokens_per_agent: int | None = None,
    ) -> None:
        self.id = str(uuid.uuid4())
        self._agents = agents
        self.mailbox = mailbox or Mailbox()
        self.task_board = task_board or TaskBoard()
        self._mission_timeout = mission_timeout
        self._max_tokens_per_agent = max_tokens_per_agent

        # Register all agents with the mailbox
        for agent in self._agents:
            self.mailbox.register(agent.id)

        # Inject team context into each agent's tools
        self._inject_team_context()

    def _inject_team_context(self) -> None:
        """Give each agent access to mailbox and task board via tool context metadata."""
        for agent in self._agents:
            agent._metadata = {
                "mailbox": self.mailbox,
                "task_board": self.task_board,
                "team_id": self.id,
                "team_agent_ids": [a.id for a in self._agents],
            }

    async def run(self, mission: str) -> TeamResult:
        """
        Launch all agents in parallel and broadcast the mission.
        Agents run until they all terminate or the timeout is reached.
        """
        # Broadcast mission to all agents
        await self.mailbox.broadcast(
            sender="team",
            subject="Mission",
            body=mission,
            mission_id=str(uuid.uuid4()),
        )

        # Also post it as a task on the board so agents can claim it
        await self.task_board.post(
            title="Mission",
            description=mission,
            posted_by="team",
        )

        # Run all agents concurrently with a global timeout
        tasks = [
            asyncio.create_task(self._run_agent(agent, mission))
            for agent in self._agents
        ]

        timed_out = False
        try:
            gather_results: list[SessionResult | BaseException] = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self._mission_timeout,
            )
        except asyncio.TimeoutError:
            timed_out = True
            for t in tasks:
                t.cancel()
            gather_results = []

        outputs: dict[str, str] = {}
        if timed_out:
            for agent in self._agents:
                outputs[agent.id] = f"Timed out after {self._mission_timeout}s"
        else:
            for agent, result in zip(self._agents, gather_results):
                if isinstance(result, Exception):
                    outputs[agent.id] = f"Error: {result}"
                elif isinstance(result, SessionResult):
                    outputs[agent.id] = result.output
                else:
                    outputs[agent.id] = str(result)

        return TeamResult(
            outputs=outputs,
            task_summary=self.task_board.summary(),
        )

    async def _run_agent(self, agent: Agent, mission: str) -> SessionResult:
        prompt = (
            f"Team mission: {mission}\n\n"
            f"Check your mailbox for messages. Use the task board to claim and complete tasks. "
            f"Coordinate with your teammates via mail. When the mission is complete, call terminate."
        )
        ctx = agent._make_ctx()
        ctx.metadata.update(agent._metadata if hasattr(agent, "_metadata") else {})
        return await agent._loop.run(prompt, ctx)

    def add_agent(self, agent: Agent) -> None:
        self._agents.append(agent)
        self.mailbox.register(agent.id)
        agent._metadata = {
            "mailbox": self.mailbox,
            "task_board": self.task_board,
            "team_id": self.id,
            "team_agent_ids": [a.id for a in self._agents],
        }

    @property
    def agents(self) -> list[Agent]:
        return list(self._agents)
