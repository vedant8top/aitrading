# AGENTS.md — Rules for Jules on this repository

This is a personal cryptocurrency trading bot intended to eventually run with
real capital. Correctness and minimal surface area matter more than feature
completeness. Follow these rules on every task, without exception:

1. **Never create a new module, package, subsystem, or top-level file unless
   the task explicitly lists it as a file to create.** If you believe a new
   file is needed to complete a task well, stop and explain why in your plan
   instead of creating it — do not create it speculatively.

2. **Touch only the files explicitly listed in the task's "Files you may
   touch" section.** If a task has no such section, ask for clarification in
   your plan before proceeding.

3. **Do not "improve while you're in there."** If you notice unrelated bugs,
   dead code, or design issues outside the task's scope, list them in your
   final PR summary under "Noticed but not fixed" — do not fix them in the
   same PR.

4. **Do not act on the "Suggested" auto-scan tab's ideas unless a task here
   explicitly asks you to implement one of them.** Suggested items are for
   human review and selection only.

5. **Every PR must include a test for the specific behavior the task
   describes.** Do not weaken or delete an existing test to make your changes
   pass — fix the regression instead, or explain in the PR why the existing
   test's expectation was wrong.

6. **This repo currently has more infrastructure than is wired together.**
   Before adding anything, check whether similar functionality already
   exists in `src/execution/`, `src/position_management/`, or `src/strategies/`.
   Prefer connecting/fixing existing code over writing new code.

7. **No live order execution changes without an explicit task requesting it.**
   Changes to anything that places real orders (`execution_engine.py`,
   `order_manager.py`, `binance_adapter.py`) require the task to say so
   explicitly by filename.
