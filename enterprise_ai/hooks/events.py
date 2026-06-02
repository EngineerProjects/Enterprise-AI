from __future__ import annotations

from enum import Enum


class HookEvent(str, Enum):
    # Session lifecycle
    session_start = "session_start"
    session_end = "session_end"

    # Query (one full agent.run() call)
    query_start = "query_start"
    query_complete = "query_complete"

    # Turn (one LLM call inside the loop)
    turn_start = "turn_start"
    turn_end = "turn_end"

    # API call
    pre_api_call = "pre_api_call"
    post_api_call = "post_api_call"

    # Tool batch (all tool calls in one turn)
    tool_uses_start = "tool_uses_start"
    tool_uses_complete = "tool_uses_complete"

    # Individual tool call — pre can block or modify input
    pre_tool_use = "pre_tool_use"
    post_tool_use = "post_tool_use"
    post_tool_use_fail = "post_tool_use_fail"

    # Compaction (context window management)
    pre_compact = "pre_compact"
    post_compact = "post_compact"

    # Permission events
    permission_request = "permission_request"
    permission_denied = "permission_denied"

    # Sub-agent lifecycle
    subagent_start = "subagent_start"
    subagent_stop = "subagent_stop"

    # Error
    on_error = "on_error"

    # Notifications (info, warning, error messages from the agent)
    notification = "notification"
