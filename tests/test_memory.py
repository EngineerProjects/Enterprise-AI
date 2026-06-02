"""
Unit tests for SessionMemory.
Tests the sliding window behavior — the only real logic here.
"""
from enterprise_ai.memory.session import SessionMemory
from enterprise_ai.schema import Message, Role


def msg(content: str) -> Message:
    return Message(role=Role.user, content=content)


def test_add_and_get():
    mem = SessionMemory()
    mem.add(msg("hello"))
    assert len(mem) == 1
    assert mem.get()[0].text() == "hello"


def test_sliding_window_evicts_oldest():
    mem = SessionMemory(max_messages=3)
    for i in range(5):
        mem.add(msg(str(i)))
    messages = mem.get()
    assert len(messages) == 3
    # oldest two are evicted
    assert [m.text() for m in messages] == ["2", "3", "4"]


def test_clear_empties_memory():
    mem = SessionMemory()
    mem.add(msg("a"))
    mem.add(msg("b"))
    mem.clear()
    assert len(mem) == 0
    assert mem.get() == []


def test_get_returns_copy_not_reference():
    mem = SessionMemory()
    mem.add(msg("original"))
    snapshot = mem.get()
    mem.add(msg("added after"))
    assert len(snapshot) == 1  # snapshot not affected


def test_order_preserved():
    mem = SessionMemory(max_messages=10)
    for i in range(5):
        mem.add(msg(str(i)))
    assert [m.text() for m in mem.get()] == ["0", "1", "2", "3", "4"]
