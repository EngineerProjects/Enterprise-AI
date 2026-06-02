---
name: systematic-debugging
description: "Debug a problem systematically by isolating root cause before fixing."
when_to_use: "When facing a bug, error, or unexpected behavior."
allowed-tools:
  - file_editor
  - code_search
  - bash
context: inline
version: "1.0.0"
---

# Systematic Debugging

Debug the problem methodically. Do NOT guess and patch — find the root cause first.

## Process

**Step 1 — Reproduce**
Confirm you can reproduce the problem consistently. Note the exact error message, stack trace, or unexpected output.

**Step 2 — Isolate**
Narrow down where the fault occurs:
- Which component, file, function?
- What inputs trigger it? What inputs don't?
- When did it start? What changed?

**Step 3 — Hypothesize**
Form 2-3 specific hypotheses about the root cause. State each clearly before testing.

**Step 4 — Test hypotheses**
Use `bash` to run targeted tests, add temporary logging, or inspect state. Test one hypothesis at a time.

**Step 5 — Identify root cause**
State the root cause in one sentence. If you can't, go back to Step 2.

**Step 6 — Fix**
Apply the minimal change that fixes the root cause. Do not clean up or refactor at the same time.

**Step 7 — Verify**
Run the reproduction case again. Confirm the fix works and no regression was introduced.

## Rules
- Never modify code before reproducing the bug
- Never apply a fix before identifying the root cause
- One hypothesis at a time
- If 3 hypotheses fail, re-examine your reproduction case
