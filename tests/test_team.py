"""
Unit tests for Team primitives: Mailbox and TaskBoard.
Team integration tests (full agent runs) are excluded — they require LLM calls.
"""
import pytest

from enterprise_ai.team.mailbox import Mail, Mailbox
from enterprise_ai.team.task_board import TaskBoard, TaskStatus

# ---------------------------------------------------------------------------
# Mailbox
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mailbox_register_and_send():
    mb = Mailbox()
    mb.register("alice")
    mb.register("bob")

    mail = Mail(sender="alice", recipients=["bob"], subject="Hello", body="Hi Bob")
    await mb.send(mail)

    received = await mb.receive("bob", timeout=0.1)
    assert received is not None
    assert received.subject == "Hello"
    assert received.body == "Hi Bob"
    assert received.read is True


@pytest.mark.asyncio
async def test_mailbox_receive_timeout_returns_none():
    mb = Mailbox()
    mb.register("alice")

    result = await mb.receive("alice", timeout=0.05)
    assert result is None


@pytest.mark.asyncio
async def test_mailbox_broadcast_reaches_all_except_sender():
    mb = Mailbox()
    for aid in ["alice", "bob", "carol"]:
        mb.register(aid)

    await mb.broadcast(sender="alice", subject="Mission", body="Build X")

    bob_mail = await mb.receive("bob", timeout=0.1)
    carol_mail = await mb.receive("carol", timeout=0.1)
    alice_mail = await mb.receive("alice", timeout=0.05)

    assert bob_mail is not None
    assert carol_mail is not None
    assert alice_mail is None  # sender doesn't receive their own broadcast


@pytest.mark.asyncio
async def test_mailbox_pending_count():
    mb = Mailbox()
    mb.register("bob")

    assert mb.pending("bob") == 0
    mail = Mail(sender="alice", recipients=["bob"], subject="A", body="B")
    await mb.send(mail)
    assert mb.pending("bob") == 1


@pytest.mark.asyncio
async def test_mailbox_history_full():
    mb = Mailbox()
    mb.register("alice")
    mb.register("bob")

    mail = Mail(sender="alice", recipients=["bob"], subject="test", body="body")
    await mb.send(mail)

    assert len(mb.history()) == 1


@pytest.mark.asyncio
async def test_mailbox_history_filtered_by_agent():
    mb = Mailbox()
    mb.register("alice")
    mb.register("bob")
    mb.register("carol")

    await mb.send(Mail(sender="alice", recipients=["bob"], subject="to bob", body=""))
    await mb.send(Mail(sender="carol", recipients=["alice"], subject="to alice", body=""))
    await mb.send(Mail(sender="bob", recipients=["carol"], subject="to carol", body=""))

    alice_history = mb.history("alice")
    assert len(alice_history) == 2  # sent one, received one


@pytest.mark.asyncio
async def test_mailbox_unknown_recipient_silently_dropped():
    mb = Mailbox()
    mb.register("alice")

    # Sending to unregistered agent — should not raise
    mail = Mail(sender="alice", recipients=["ghost"], subject="x", body="y")
    await mb.send(mail)
    assert len(mb.history()) == 1


# ---------------------------------------------------------------------------
# TaskBoard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_task_board_post_and_claim():
    board = TaskBoard()
    task = await board.post("Build API", "Create a REST API", posted_by="manager")

    assert task.status == TaskStatus.pending
    assert board.summary() == "pending: 1"

    claimed = await board.claim(task.id, "developer")
    assert claimed is not None
    assert claimed.status == TaskStatus.claimed
    assert claimed.claimed_by == "developer"


@pytest.mark.asyncio
async def test_task_board_claim_already_claimed_returns_none():
    board = TaskBoard()
    task = await board.post("Task", "desc", posted_by="manager")
    await board.claim(task.id, "developer1")

    result = await board.claim(task.id, "developer2")
    assert result is None


@pytest.mark.asyncio
async def test_task_board_complete():
    board = TaskBoard()
    task = await board.post("Task", "desc", posted_by="manager")
    await board.claim(task.id, "developer")

    ok = await board.complete(task.id, result="API implemented")
    assert ok is True
    assert board.get(task.id).status == TaskStatus.done
    assert board.get(task.id).result == "API implemented"


@pytest.mark.asyncio
async def test_task_board_fail():
    board = TaskBoard()
    task = await board.post("Task", "desc", posted_by="manager")
    await board.claim(task.id, "developer")

    ok = await board.fail(task.id, reason="Blocked by missing dep")
    assert ok is True
    assert board.get(task.id).status == TaskStatus.failed


@pytest.mark.asyncio
async def test_task_board_claim_next():
    board = TaskBoard()
    await board.post("Task 1", "first", posted_by="manager")
    await board.post("Task 2", "second", posted_by="manager")

    t1 = await board.claim_next("developer")
    assert t1 is not None
    assert t1.status == TaskStatus.claimed

    assert len(board.pending_tasks()) == 1


@pytest.mark.asyncio
async def test_task_board_claim_next_no_tasks_returns_none():
    board = TaskBoard()
    result = await board.claim_next("developer", timeout=0.05)
    assert result is None


@pytest.mark.asyncio
async def test_task_board_tasks_by_agent():
    board = TaskBoard()
    t1 = await board.post("T1", "", posted_by="manager")
    t2 = await board.post("T2", "", posted_by="manager")
    await board.post("T3", "", posted_by="manager")

    await board.claim(t1.id, "dev-a")
    await board.claim(t2.id, "dev-a")

    assert len(board.tasks_by("dev-a")) == 2
    assert len(board.tasks_by("dev-b")) == 0


@pytest.mark.asyncio
async def test_task_board_summary():
    board = TaskBoard()
    t1 = await board.post("T1", "", posted_by="manager")
    t2 = await board.post("T2", "", posted_by="manager")
    await board.post("T3", "", posted_by="manager")

    await board.claim(t1.id, "dev")
    await board.complete(t1.id, result="done")
    await board.claim(t2.id, "dev")

    summary = board.summary()
    assert "done: 1" in summary
    assert "claimed: 1" in summary
    assert "pending: 1" in summary
