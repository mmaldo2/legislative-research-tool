"""Condorcet Lab — Family 1 code-graded benchmark harness.

A frozen, task-eval-shaped harness (NL question -> answer -> code-graded pass/fail)
mirroring autoresearch/'s frozen-core + gold-by-SQL discipline. Gold is computed by
trusted, engine-portable SQL over the roll-call vote tables; the frozen core
(harness, templates' gold SQL, graders) is never modified to make a task pass.
"""
