---
name: test-driven-development
description: "Write tests before implementation — red/green/refactor cycle."
when_to_use: "When implementing a new feature or fixing a bug."
allowed-tools:
  - file_editor
  - code_search
  - bash
context: inline
version: "1.0.0"
---

# Test-Driven Development

Follow the red/green/refactor cycle strictly.

## Cycle

**Red — Write a failing test first**
1. Understand what the code should do (ask if unclear)
2. Write the simplest test that captures the requirement
3. Run it — confirm it FAILS for the right reason
4. If it passes immediately, the test is wrong or the feature already exists

**Green — Make it pass with minimal code**
1. Write the minimum code to make the test pass
2. No premature optimization, no extra features
3. Run the test — confirm it PASSES

**Refactor — Clean up without breaking**
1. Improve structure, naming, remove duplication
2. Run tests after every change
3. All tests must still pass after refactoring

## Rules
- Never write implementation before a failing test exists
- Tests should test behavior, not implementation details
- One failing test at a time — don't write multiple tests before making the first one pass
- Each test should test exactly one thing

## Test naming
```
test_{what}_{condition}_{expected_result}
# Examples:
test_auth_with_expired_token_returns_401
test_user_creation_with_duplicate_email_raises_error
```
