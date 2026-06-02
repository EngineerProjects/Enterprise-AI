"""
Default prompt strings used internally by enterprise-ai.

Override any of these at import time to customise agent behaviour:

    import enterprise_ai.prompt.templates as tpl
    tpl.COMPACTION_PROMPT = "Résume en français : {messages_text}"
    tpl.BUDGET_NUDGE_MESSAGE = "Poursuis la tâche."
"""
from __future__ import annotations

COMPACTION_PROMPT: str = """\
You are summarizing a conversation to reduce context length.
Summarize the following conversation turns into a concise paragraph.
Preserve: key decisions made, important facts discovered, current task state, \
tool results that matter.
Do NOT preserve: verbose tool outputs, redundant exchanges, greetings.
Target length: under 500 words.

<conversation>
{messages_text}
</conversation>"""

BUDGET_NUDGE_MESSAGE: str = "Continue with the task."

SPAWN_DEFAULT_SYSTEM: str = (
    "You are a specialized sub-agent. Complete the task and call terminate when done."
)
