# Contributing to enterprise-ai

> **Français** : une version française de ce guide est disponible dans [CONTRIBUTING.fr.md](CONTRIBUTING.fr.md).

Thank you for your interest in contributing. This guide covers everything you need to know to contribute effectively.

---

## Table of contents

1. [Code of conduct](#1-code-of-conduct)
2. [Ways to contribute](#2-ways-to-contribute)
3. [Setting up your environment](#3-setting-up-your-environment)
4. [Git workflow](#4-git-workflow)
5. [Code standards](#5-code-standards)
6. [Tests](#6-tests)
7. [Project structure](#7-project-structure)
8. [Dependency rules](#8-dependency-rules)
9. [Commit messages](#9-commit-messages)
10. [Opening a Pull Request](#10-opening-a-pull-request)
11. [Reporting a bug](#11-reporting-a-bug)
12. [Proposing a feature](#12-proposing-a-feature)

---

## 1. Code of conduct

This project enforces a simple code of conduct: **respect and professionalism**.

- Critique the code, never the person
- Beginner questions are welcome
- Technical discussions stay factual
- Any form of harassment results in immediate exclusion

---

## 2. Ways to contribute

### Gladly accepted

- Bug fixes with a non-regression test
- New LLM providers (OpenAI-compatible or native)
- New builtin tools (`enterprise_ai/tools/builtin/`)
- Documentation improvements
- Clearer error messages
- Measurable performance improvements

### Requires prior discussion

- Major new features → open an issue first
- Public API changes → mandatory discussion
- New core dependencies → justification required

### Not accepted

- Code without tests
- Unpinned dependencies in `pyproject.toml`
- Breaking changes without a migration path
- Code that reduces existing test coverage

---

## 3. Setting up your environment

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package manager)

### Installation

```bash
git clone https://github.com/your-org/enterprise-ai.git
cd enterprise-ai

# Create the virtual environment and install all dev dependencies
make setup_uv

# Verify everything works
make test
```

### Environment variables

```bash
export ANTHROPIC_API_KEY="sk-ant-..."   # for integration tests (optional)
```

Unit tests do not require an API key — everything is mocked.

---

## 4. Git workflow

### Branches

| Branch | Role |
|---|---|
| `main` | Stable code — releases only |
| `dev` | Main development branch — PRs target here |

### Creating a working branch

```bash
git checkout dev
git pull origin dev
git checkout -b feat/my-new-thing
# or
git checkout -b fix/bug-description
git checkout -b docs/what-changes
```

### Branch naming conventions

```
feat/short-name        new feature
fix/short-name         bug fix
docs/short-name        documentation only
refactor/short-name    refactoring without functional change
chore/short-name       maintenance (deps, CI, config)
test/short-name        adding or fixing tests
```

---

## 5. Code standards

### Formatting and linting

```bash
make format    # ruff format + ruff check --fix
make lint      # ruff check + mypy
```

All code must pass without errors before opening a PR.

### Key rules

**Type annotations — mandatory**

All source code in `enterprise_ai/` must be annotated. mypy must report zero errors.

```python
# Good
async def complete(self, messages: list[Message], tools: list[ToolSchema] | None = None) -> LLMResponse:

# Bad
async def complete(self, messages, tools=None):
```

**Comments — minimal**

Only comment what is not obvious from the code itself. No multi-paragraph docstrings, no comments that restate what a variable name already says.

```python
# Good — explains a non-obvious invariant
# Rotation without delay: the retry loop only sees one 429 per full pool cycle
if getattr(exc, "status_code", None) == 429 and not self._pool.rotate():
    continue

# Bad — restates what the code already says
# Iterate over messages and add each one to memory
for msg in messages:
    self._memory.add(msg)
```

**No over-engineering**

- Three similar lines are better than a premature abstraction
- Do not add parameters "for the future"
- Do not create helper files for a single function

**Error handling**

- Validate only at system boundaries (user input, external APIs)
- Trust internal framework guarantees
- Do not catch bare `Exception` unless documented

**Imports**

- stdlib, then third-party, then project — separated by a blank line
- Defer local imports inside functions to avoid circular imports

```python
from __future__ import annotations  # always first

import asyncio                       # stdlib
from typing import Any

import httpx                         # third-party

from enterprise_ai.schema import Message  # project
```

**Async**

- All I/O must be `async`
- Never use `time.sleep()` in async code — use `asyncio.sleep()`
- Async generators must have a `yield` even if they never yield (to satisfy mypy)

---

## 6. Tests

### Running tests

```bash
make test                                          # all tests
uv run pytest tests/test_my_module.py -v           # single file
uv run pytest -k "test_my_function" -v             # single test
uv run pytest --cov=enterprise_ai                  # with coverage
```

### Test rules

**Every PR must include tests.** No code without a test, no exceptions.

**Test file structure**

```python
"""Tests for MyModule — short description."""
from __future__ import annotations

import pytest
from enterprise_ai.my_module import MyClass


# ── Section 1 — Basic behavior ───────────────────────────────────────────────

def test_normal_case():
    obj = MyClass(param="value")
    assert obj.result == "expected"


def test_edge_case():
    ...


# ── Section 2 — Async behavior ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_async_flow():
    ...
```

**Mocking**

- Mock LLM API calls using a fake `Provider` (see examples in `tests/`)
- Never make real network calls in unit tests
- Use `unittest.mock.patch` for external dependencies

**Fake Provider pattern** (project standard)

```python
from typing import AsyncIterator
from enterprise_ai.providers.base import LLMResponse, Provider
from enterprise_ai.schema import StreamEvent

class FakeProvider(Provider):
    @property
    def model(self) -> str:
        return "fake"

    async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
        return LLMResponse(content="simulated response", tool_calls=[])

    async def stream(self, *a, **kw) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError
        yield  # makes the function an async generator for mypy
```

**Coverage**

Overall coverage must not decrease. Aim for > 80% on each new module.

```bash
uv run pytest --cov=enterprise_ai --cov-report=html
open htmlcov/index.html
```

---

## 7. Project structure

```
enterprise_ai/
├── agent/          # Agent, MixtureOfAgents
├── engine/         # QueryLoop, StopHooks, TokenBudget
├── execution/      # Orchestrator, StreamingExecutor
├── hooks/          # HookRegistry, HookExecutor, HookEvent
├── mcp/            # MCPManager, MCPClient, configs
├── memory/         # SessionMemory, LongTermMemory, ContextEngine
├── modes/          # ExecutionMode
├── permissions/    # PermissionEngine
├── prompt/         # PromptBuilder, cache helpers, templates
├── providers/      # AnthropicProvider, OpenAIProvider, retry, errors
├── sandbox/        # LocalSandbox, DockerSandbox
├── schema/         # Message, ToolCall, StreamEvent, SessionResult
├── skills/         # Skill, SkillCurator, preprocessing
├── stream/         # StreamScrubber, TagScrubber
├── team/           # Team, Mailbox, TaskBoard
└── tools/
    ├── builtin/    # BashTool, FileEditorTool, WebSearchTool, ...
    ├── contract.py # BaseTool ABC
    ├── registry.py
    ├── toolsets.py
    └── search_bridge.py
```

### Adding a builtin tool

1. Create `enterprise_ai/tools/builtin/my_tool.py`
2. Export it from `enterprise_ai/tools/builtin/__init__.py`
3. Register it in `_builtin_factories()` in `toolsets.py` if applicable
4. Create `tests/test_my_tool.py`

### Adding a provider

1. Create `enterprise_ai/providers/my_provider.py` — implement `Provider`
2. Register it in `enterprise_ai/providers/factory.py` (if applicable)
3. Export it from `enterprise_ai/providers/__init__.py`
4. Add dependencies to `pyproject.toml` (as extras if not core)

---

## 8. Dependency rules

### Core dependencies (in `dependencies`)

Only packages needed by **every agent session**. Pinned to exact version (`==X.Y.Z`).

```toml
# Good
"anthropic==0.49.0"

# Bad
"anthropic>=0.49.0"
"anthropic"
```

### Optional extras

Providers, search backends, sandboxes → in `[project.optional-dependencies]`.

### Adding a dependency

1. Justify why it is needed (do not add for a single use case)
2. Verify it is actively maintained
3. Pin the exact version
4. Regenerate the lock file: `uv lock`
5. Document the extra in `pyproject.toml` and `docs/quickstart.md`

### Deferred imports for extras

If a dependency is optional, import it inside the function with a clear error message:

```python
def _get_qdrant_client(self):
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        raise ImportError(
            "qdrant-client is required for VectorMemory with the Qdrant backend. "
            "Install it with: pip install 'enterprise-ai[qdrant]'"
        )
    return QdrantClient(...)
```

---

## 9. Commit messages

Format: `type: short description`

### Valid types

| Type | When |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Refactoring without functional change |
| `test` | Adding or fixing tests |
| `chore` | Maintenance (deps, CI, config, build) |
| `perf` | Performance improvement |

### Rules

```bash
# Good
feat: add SkillCurator for post-session skill extraction
fix: TagScrubber handles tags split across chunk boundaries
docs: document MixtureOfAgents aggregation strategies

# Bad
fix stuff
WIP
update code
feat: Add a new super cool feature that does many things and also fixes bugs
```

- Title line: max 72 characters
- Present tense, imperative mood ("add", not "added" or "adds")
- Optional body to explain the *why* (not the *what*)

---

## 10. Opening a Pull Request

### Before opening

```bash
make lint    # ruff + mypy: 0 errors
make test    # all tests pass
```

### PR checklist

- [ ] Tests added for every new behavior
- [ ] `make lint` passes with no errors
- [ ] `make test` passes with no errors
- [ ] Coverage has not decreased
- [ ] Documentation updated if the public API changes
- [ ] PR title follows the `type: description` format
- [ ] Target branch is `dev` (never `main` directly)

### Description template

```markdown
## Context

Brief description of the problem or feature.

## Changes

- What was added / modified / removed
- ...

## Tests

Describe the tests added and how to run them.

## Notes for reviewers

Highlight any areas that deserve special attention.
```

### Review process

- At least 1 approval required before merge
- Review comments must be addressed (resolved or discussed)
- PRs open for more than 30 days without activity are closed

---

## 11. Reporting a bug

Open an issue using the following template:

```markdown
**Version**: enterprise-ai X.Y.Z
**Python**: 3.11 / 3.12 / 3.13
**OS**: Linux / macOS / Windows

**Description**
What happens vs. what should happen.

**Minimal reproduction**
```python
# Minimal code that reproduces the bug
```

**Traceback**
```
Paste the full stack trace here
```

**Additional context**
Anything else that might help.
```

---

## 12. Proposing a feature

Open an issue with:

1. **The problem**: what need is currently unmet?
2. **The proposed solution**: how you intend to implement it
3. **Alternatives**: other approaches considered and why you ruled them out
4. **Impact**: who benefits, does anything break?

Major features are discussed **before** any code is written. Open the issue first, code second.

---

## Questions?

- Open an issue with the `question` label
- Check the [documentation](docs/README.md) first
