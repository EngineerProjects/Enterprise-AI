"""
Unit tests for team tools: SendMailTool, ReadMailTool, PostTaskTool, ClaimTaskTool, etc.
Uses real Mailbox and TaskBoard — no mocking needed, they're pure async.
"""
import pytest

from enterprise_ai.team.mailbox import Mailbox
from enterprise_ai.team.task_board import TaskBoard, TaskStatus
from enterprise_ai.tools.builtin.mail import MailboxStatusTool, ReadMailTool, SendMailTool
from enterprise_ai.tools.builtin.task import (
    ClaimTaskTool,
    CompleteTaskTool,
    FailTaskTool,
    ListTasksTool,
    PostTaskTool,
)
from enterprise_ai.tools.context import ToolContext


def make_ctx(agent_id: str, mailbox: Mailbox | None = None, task_board: TaskBoard | None = None) -> ToolContext:
    ctx = ToolContext(agent_id=agent_id)
    if mailbox:
        ctx.metadata["mailbox"] = mailbox
    if task_board:
        ctx.metadata["task_board"] = task_board
    return ctx


# ---------------------------------------------------------------------------
# Mail tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_mail_tool():
    mb = Mailbox()
    mb.register("alice")
    mb.register("bob")

    tool = SendMailTool()
    inp = SendMailTool.input_schema(to=["bob"], subject="Hello", body="Hi Bob!")
    ctx = make_ctx("alice", mailbox=mb)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert "bob" in result.content

    mail = await mb.receive("bob", timeout=0.1)
    assert mail is not None
    assert mail.subject == "Hello"


@pytest.mark.asyncio
async def test_send_mail_tool_no_mailbox():
    tool = SendMailTool()
    inp = SendMailTool.input_schema(to=["bob"], subject="x", body="y")
    ctx = make_ctx("alice")  # no mailbox

    result = await tool.call(inp, ctx)
    assert result.is_error


@pytest.mark.asyncio
async def test_read_mail_tool_with_mail():
    mb = Mailbox()
    mb.register("bob")

    from enterprise_ai.team.mailbox import Mail
    await mb.send(Mail(sender="alice", recipients=["bob"], subject="News", body="Done!"))

    tool = ReadMailTool()
    inp = ReadMailTool.input_schema(timeout=0.1)
    ctx = make_ctx("bob", mailbox=mb)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert "News" in result.content
    assert "Done!" in result.content


@pytest.mark.asyncio
async def test_read_mail_tool_empty_inbox():
    mb = Mailbox()
    mb.register("bob")

    tool = ReadMailTool()
    inp = ReadMailTool.input_schema(timeout=0.0)
    ctx = make_ctx("bob", mailbox=mb)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert "No mail" in result.content


@pytest.mark.asyncio
async def test_mailbox_status_tool():
    mb = Mailbox()
    mb.register("bob")

    from enterprise_ai.team.mailbox import Mail
    await mb.send(Mail(sender="alice", recipients=["bob"], subject="A", body=""))
    await mb.send(Mail(sender="alice", recipients=["bob"], subject="B", body=""))

    tool = MailboxStatusTool()
    inp = MailboxStatusTool.input_schema()
    ctx = make_ctx("bob", mailbox=mb)

    result = await tool.call(inp, ctx)
    assert "2" in result.content


# ---------------------------------------------------------------------------
# Task tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_task_tool():
    board = TaskBoard()
    tool = PostTaskTool()
    inp = PostTaskTool.input_schema(title="Build API", description="Create REST endpoints")
    ctx = make_ctx("manager", task_board=board)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert "Build API" in result.content
    assert len(board.pending_tasks()) == 1


@pytest.mark.asyncio
async def test_claim_task_tool_by_id():
    board = TaskBoard()
    task = await board.post("Fix bug", "Resolve issue #42", posted_by="manager")

    tool = ClaimTaskTool()
    inp = ClaimTaskTool.input_schema(task_id=task.id)
    ctx = make_ctx("dev", task_board=board)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert "Fix bug" in result.content
    assert board.get(task.id).claimed_by == "dev"


@pytest.mark.asyncio
async def test_claim_task_tool_next():
    board = TaskBoard()
    await board.post("Task A", "desc", posted_by="manager")

    tool = ClaimTaskTool()
    inp = ClaimTaskTool.input_schema()  # no task_id = claim next
    ctx = make_ctx("dev", task_board=board)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert "Task A" in result.content


@pytest.mark.asyncio
async def test_claim_task_tool_empty_board():
    board = TaskBoard()
    tool = ClaimTaskTool()
    inp = ClaimTaskTool.input_schema(timeout=0.0)
    ctx = make_ctx("dev", task_board=board)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert "No task" in result.content


@pytest.mark.asyncio
async def test_complete_task_tool():
    board = TaskBoard()
    task = await board.post("Task", "desc", posted_by="manager")
    await board.claim(task.id, "dev")

    tool = CompleteTaskTool()
    inp = CompleteTaskTool.input_schema(task_id=task.id, result="Done — API implemented")
    ctx = make_ctx("dev", task_board=board)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert board.get(task.id).status == TaskStatus.done


@pytest.mark.asyncio
async def test_fail_task_tool():
    board = TaskBoard()
    task = await board.post("Task", "desc", posted_by="manager")
    await board.claim(task.id, "dev")

    tool = FailTaskTool()
    inp = FailTaskTool.input_schema(task_id=task.id, reason="Blocked — missing credentials")
    ctx = make_ctx("dev", task_board=board)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert board.get(task.id).status == TaskStatus.failed


@pytest.mark.asyncio
async def test_list_tasks_tool_pending():
    board = TaskBoard()
    await board.post("T1", "", posted_by="manager")
    await board.post("T2", "", posted_by="manager")
    t3 = await board.post("T3", "", posted_by="manager")
    await board.claim(t3.id, "dev")

    tool = ListTasksTool()
    inp = ListTasksTool.input_schema(filter="pending")
    ctx = make_ctx("manager", task_board=board)

    result = await tool.call(inp, ctx)
    assert "T1" in result.content
    assert "T2" in result.content
    assert "T3" not in result.content  # T3 is claimed, not pending


@pytest.mark.asyncio
async def test_list_tasks_tool_mine():
    board = TaskBoard()
    t1 = await board.post("Mine", "", posted_by="manager")
    await board.post("Not mine", "", posted_by="manager")
    await board.claim(t1.id, "dev")

    tool = ListTasksTool()
    inp = ListTasksTool.input_schema(filter="mine")
    ctx = make_ctx("dev", task_board=board)

    result = await tool.call(inp, ctx)
    assert "Mine" in result.content
    assert "Not mine" not in result.content
