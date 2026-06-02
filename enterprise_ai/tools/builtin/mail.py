from __future__ import annotations

from pydantic import BaseModel, Field

from enterprise_ai.schema import ToolResult
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool


class SendMailInput(BaseModel):
    to: list[str] = Field(description="List of recipient agent IDs.")
    subject: str = Field(description="Subject of the message.")
    body: str = Field(description="Message body.")


class ReadMailInput(BaseModel):
    timeout: float = Field(default=0.0, ge=0.0, description="Seconds to wait for mail. 0 = return immediately.")


class MailboxStatusInput(BaseModel):
    pass


class SendMailTool(BaseTool):
    name = "send_mail"
    description = (
        "Send a message to one or more teammates. "
        "Use to share findings, ask for help, delegate sub-tasks, or coordinate actions. "
        "Recipient IDs are the agent IDs of your teammates (available in your context)."
    )
    input_schema = SendMailInput

    async def call(self, input: SendMailInput, ctx: ToolContext) -> ToolResult:
        mailbox = ctx.metadata.get("mailbox")
        if mailbox is None:
            return ToolResult.error(tool_call_id="", name=self.name, error="No mailbox in context — agent is not in a team.")

        from enterprise_ai.team.mailbox import Mail
        mail = Mail(sender=ctx.agent_id, recipients=input.to, subject=input.subject, body=input.body)
        await mailbox.send(mail)
        return ToolResult.ok(
            tool_call_id="", name=self.name,
            content=f"Mail sent to {', '.join(input.to)} | Subject: {input.subject}",
        )


class ReadMailTool(BaseTool):
    name = "read_mail"
    description = (
        "Read the next message from your inbox. "
        "Returns the message or 'No mail' if inbox is empty. "
        "Set timeout > 0 to wait for incoming mail."
    )
    input_schema = ReadMailInput

    async def call(self, input: ReadMailInput, ctx: ToolContext) -> ToolResult:
        mailbox = ctx.metadata.get("mailbox")
        if mailbox is None:
            return ToolResult.error(tool_call_id="", name=self.name, error="No mailbox in context — agent is not in a team.")

        timeout = input.timeout if input.timeout > 0 else None
        mail = await mailbox.receive(ctx.agent_id, timeout=timeout)
        if mail is None:
            pending = mailbox.pending(ctx.agent_id)
            return ToolResult.ok(tool_call_id="", name=self.name, content=f"No mail. ({pending} pending)")

        return ToolResult.ok(tool_call_id="", name=self.name, content=str(mail))


class MailboxStatusTool(BaseTool):
    name = "mailbox_status"
    description = "Check how many unread messages are in your inbox."
    input_schema = MailboxStatusInput

    async def call(self, input: MailboxStatusInput, ctx: ToolContext) -> ToolResult:
        mailbox = ctx.metadata.get("mailbox")
        if mailbox is None:
            return ToolResult.error(tool_call_id="", name=self.name, error="No mailbox in context.")
        pending = mailbox.pending(ctx.agent_id)
        return ToolResult.ok(tool_call_id="", name=self.name, content=f"{pending} unread message(s) in inbox.")
