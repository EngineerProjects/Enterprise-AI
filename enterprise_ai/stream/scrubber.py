"""
Streaming scrubbers — stateful text filters applied chunk-by-chunk.

A scrubber strips content between configurable open/close tags, even when
those tags are split across multiple stream chunks. State persists between
calls to process() within the same turn; call reset() between turns.

Usage:
    agent = Agent(
        provider=...,
        stream_scrubbers=[
            TagScrubber("<memory-context>", "</memory-context>"),
        ],
    )
    async for event in agent.stream("What do you remember about me?"):
        # memory-context blocks are stripped from text_delta events
        print(event)

    # Custom scrubber:
    from enterprise_ai.stream import TagScrubber
    scrubber = TagScrubber("<internal>", "</internal>")
    visible = scrubber.process("some <internal>hidden</internal> text")
    # → "some  text"
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class StreamScrubber(ABC):
    """
    Stateful filter applied to text stream chunks.

    Call process(chunk) for each incoming text delta.
    Call reset() between turns to clear partial-match state.
    """

    @abstractmethod
    def process(self, chunk: str) -> str:
        """
        Process one chunk of stream text.
        Returns the visible portion (filtered content removed).
        """

    @abstractmethod
    def reset(self) -> None:
        """Reset state. Call between agent turns."""

    @property
    @abstractmethod
    def in_block(self) -> bool:
        """True while the scrubber is inside a filtered block."""


class TagScrubber(StreamScrubber):
    """
    Strips content between an open tag and a close tag.

    Handles tags split across chunk boundaries by buffering partial matches.
    Nested identical tags are NOT supported — the first close tag ends the block.

    Example:
        scrubber = TagScrubber("<think>", "</think>")
        scrubber.process("Hello <thi")   → "Hello "
        scrubber.process("nk>hidden")    → ""
        scrubber.process("</think> world") → " world"
    """

    def __init__(self, open_tag: str, close_tag: str) -> None:
        self._open = open_tag
        self._close = close_tag
        self._in_block = False
        self._buf = ""   # partial tag match buffered across chunk boundary

    @property
    def in_block(self) -> bool:
        return self._in_block

    def reset(self) -> None:
        self._in_block = False
        self._buf = ""

    def process(self, chunk: str) -> str:
        text = self._buf + chunk
        self._buf = ""
        out: list[str] = []

        while text:
            if not self._in_block:
                tag = self._open
                idx = text.find(tag)
                if idx == -1:
                    # Full open tag not found — check for partial match at end
                    partial = self._partial_prefix(text, tag)
                    if partial:
                        out.append(text[: len(text) - len(partial)])
                        self._buf = partial
                    else:
                        out.append(text)
                    break
                out.append(text[:idx])
                text = text[idx + len(tag):]
                self._in_block = True
            else:
                tag = self._close
                idx = text.find(tag)
                if idx == -1:
                    # Full close tag not found — check for partial match at end
                    partial = self._partial_prefix(text, tag)
                    if partial:
                        self._buf = partial
                    # Content inside block is consumed (not emitted)
                    break
                # Skip content up to and including the close tag
                text = text[idx + len(tag):]
                self._in_block = False

        return "".join(out)

    @staticmethod
    def _partial_prefix(text: str, tag: str) -> str:
        """
        Return the longest suffix of `text` that is a prefix of `tag`.
        Used to detect partial tag matches at chunk boundaries.
        """
        for length in range(min(len(tag) - 1, len(text)), 0, -1):
            if text.endswith(tag[:length]):
                return tag[:length]
        return ""
