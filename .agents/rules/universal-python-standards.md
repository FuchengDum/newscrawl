---
trigger: always_on
---

# Universal Python Coding Standards

## 1. Code Quality & Maintenance (Always On)
* **PEP 8 Compliance**: Strictly adhere to PEP 8. Use 4-space indentation and maintain clear, readable code structures.
* **Type Hinting (Mandatory)**: All function signatures must include full type hints (e.g., `def process(data: List[str]) -> Dict[str, Any]:`). Use the `typing` module or modern built-in generics.
* **Docstrings**: Every function and class must include a Google-style docstring explaining purpose, arguments, and return types.
* **Minimalistic Imports**: Avoid unnecessary dependencies. Prefer built-in libraries (`pathlib`, `json`, `argparse`, `logging`) over external packages unless essential.

## 2. Robust Development Practices (Skill Integration)
* **Skill Integration (TDD)**: When `test-driven-development` is active, write the test case first. Ensure test coverage for edge cases (empty inputs, API failures).
* **Skill Integration (Debugging)**: When `systematic-debugging` is active, avoid print-statement debugging. Use `logging` with appropriate levels (`DEBUG`, `INFO`, `ERROR`).
* **Skill Integration (Verification)**: When `verification-before-completion` is active, self-audit the code against this Rule file before indicating completion.

## 3. Pythonic Error Handling
* **Explicit Exceptions**: Never use naked `except:` blocks. Always catch specific exceptions (e.g., `ValueError`, `FileNotFoundError`) and provide meaningful error messages.
* **Resource Management**: Always use context managers (`with` statements) for file I/O, network sockets, or database connections.

## 4. Workflow & Branch Discipline
* **Git Worktree Discipline**: When `using-git-worktrees` is active, ensure all temporary changes or parallel experiments are isolated in dedicated worktrees.
* **Branch Integrity**: When `finishing-a-development-branch` is active, ensure all tests pass and documentation is updated before finalizing the merge.