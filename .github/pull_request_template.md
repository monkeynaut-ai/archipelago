## What and why

<!-- What changes, and what problem it solves. Link the issue if there is one. -->

## How it was verified

<!--
Paste the result of `pdm test-all`. A skipped integration test (no Docker, for
instance) is acceptable; a failure is not. Do not claim the suite passes without
having run it.
-->

## Checklist

- [ ] Tests were written before the implementation (red, green, refactor)
- [ ] `pdm test-all` passes
- [ ] `pdm lint`, `pdm format`, and `pdm typecheck` are clean
- [ ] No test asserts on pipeline topology — composition, step counts, wiring, or which state model a field lives on
- [ ] Agent Foundry symbols are imported from package facades, not deep modules
- [ ] Docs updated if behavior or workflow changed
