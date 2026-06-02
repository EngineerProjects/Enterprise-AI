from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Mail:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""
    recipients: list[str] = field(default_factory=list)
    subject: str = ""
    body: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    read: bool = False

    def mark_read(self) -> None:
        self.read = True

    def __str__(self) -> str:
        ts = self.sent_at.strftime("%H:%M:%S")
        return f"[{ts}] From:{self.sender} To:{','.join(self.recipients)} | {self.subject}\n{self.body}"


class Mailbox:
    """
    Shared async message bus for a team of agents.

    Each agent has its own inbox (queue). Agents send mail to one or
    multiple recipients. A broadcast sends to all registered agents.

    This is the primary coordination primitive — agents communicate
    via mail rather than direct calls, just like a real organization.
    """

    def __init__(self) -> None:
        self._inboxes: dict[str, asyncio.Queue[Mail]] = {}
        self._history: list[Mail] = []
        self._lock = asyncio.Lock()

    def register(self, agent_id: str) -> None:
        if agent_id not in self._inboxes:
            self._inboxes[agent_id] = asyncio.Queue()

    async def send(self, mail: Mail) -> None:
        async with self._lock:
            self._history.append(mail)
        for recipient in mail.recipients:
            if recipient in self._inboxes:
                await self._inboxes[recipient].put(mail)

    async def broadcast(self, sender: str, subject: str, body: str, **metadata: Any) -> None:
        recipients = [aid for aid in self._inboxes if aid != sender]
        mail = Mail(sender=sender, recipients=recipients, subject=subject, body=body, metadata=metadata)
        await self.send(mail)

    async def receive(self, agent_id: str, timeout: float | None = None) -> Mail | None:
        """Read next mail for agent_id. Returns None on timeout."""
        if agent_id not in self._inboxes:
            return None
        try:
            mail = await asyncio.wait_for(self._inboxes[agent_id].get(), timeout=timeout)
            mail.mark_read()
            return mail
        except asyncio.TimeoutError:
            return None

    def pending(self, agent_id: str) -> int:
        """Number of unread mails in an agent's inbox."""
        if agent_id not in self._inboxes:
            return 0
        return self._inboxes[agent_id].qsize()

    def history(self, agent_id: str | None = None) -> list[Mail]:
        """Full message history, optionally filtered to messages involving agent_id."""
        if agent_id is None:
            return list(self._history)
        return [m for m in self._history if m.sender == agent_id or agent_id in m.recipients]

    @property
    def agents(self) -> list[str]:
        return list(self._inboxes.keys())
