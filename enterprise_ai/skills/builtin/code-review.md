---
name: code-review
description: "Review code for correctness, security, performance and style."
when_to_use: "When asked to review code, audit a PR, or check a file before merging."
allowed-tools:
  - file_editor
  - code_search
  - bash
context: inline
version: "1.0.0"
---

# Code Review

Review the provided code systematically across four dimensions:

## 1. Correctness
- Logic errors, off-by-one mistakes, edge cases not handled
- Incorrect assumptions about input types or ranges
- Race conditions or concurrency issues

## 2. Security
- Injection vulnerabilities (SQL, command, path traversal)
- Missing input validation or authentication checks
- Hardcoded secrets or credentials
- Exposed sensitive data in logs or responses

## 3. Performance
- Unnecessary loops or database queries (N+1 problem)
- Missing indexes or inefficient data structures
- Blocking calls in async code

## 4. Style & Maintainability
- Unclear naming or missing documentation for non-obvious behavior
- Functions doing too many things (single responsibility)
- Dead code or unused imports

## Output format

For each finding:
- **File:line** — what the issue is
- **Why** — why it matters
- **Fix** — concrete suggestion

End with a summary: overall assessment (✅ good / ⚠️ needs work / ❌ blocking issues) and the top 3 priority fixes if any.
