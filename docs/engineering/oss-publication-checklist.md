# OSS publication checklist

Tracking the work to take Archipelago from a private repo to a public one.
Repo is **private** as of 2026-07-19.

## Done

- [x] **1. Agent Foundry dependency** — decided: depend on the published
      `agent-foundry-ai` package from PyPI (`>=0.12.0`). The sibling-checkout
      `file://` dependency was tried first for lockstep convenience, but a path
      dependency has no version to lock, so CI and a fresh clone could not be made
      reproducible. The version now lands in `pdm.lock` with hashes.
- [x] **2. Agent Foundry visibility** — public at `github.com/monkeynaut-ai/agent-foundry`.
      Also published to PyPI as `agent-foundry-ai` 0.12.0 (unused by Archipelago
      under decision 1).
- [x] **3. LICENSE** — Apache-2.0, matching Agent Foundry. `pyproject.toml` updated.
- [x] **4. Secret-scan full history** — both repos, every blob on every ref. Clean:
      no provider tokens, no credential assignments, no secret-bearing files ever
      added (`.env.example` only, placeholders verified). Regex-based, no entropy
      pass.
- [x] **5. Rotate leaked credentials** — nothing leaked, so nothing to rotate.
      `ADD_TO_PROJECT_PAT` repo secret deleted and the PAT revoked.
- [x] **6. Audit workflows for fork-PR secret exposure** — `add-to-project.yml`
      deleted; Archipelago now has zero workflows and zero repo secrets.
- [x] **12. README** — rewritten for an outside reader.
- [x] **13. CONTRIBUTING.md**
- [x] **14. SECURITY.md** — includes an in-scope/out-of-scope threat model, since
      "the agent wrote code and pushed it" is the product, not a vulnerability.
- [x] **15. CODE_OF_CONDUCT.md** — Contributor Covenant 2.1.
- [x] **16. Issue and PR templates** — `.github/ISSUE_TEMPLATE/` + `pull_request_template.md`.
- [x] **17. Repo metadata** — description and topics set. Homepage empty.
- [x] **18. Status banner** — experimental / no-support warning at the top of the README.
- [x] **8. Prune tracked scratch files** — removed `temp/` (agent `.py.save` fossils, notes
      moved to `docs/temp/`), `src/archipelago/docker/` (orphaned role-instruction files),
      `claude/` (a stray copy of user-level Claude Code config), the empty
      `tests/archipelago/{unit,integration}/`, `project-check-2026-04-29.md`,
      `job-add-review.md`, and `docs/product/system-level-context.md`.
- [x] **9. `lab/`, `runs/`, `team/`** — `lab/` and `team/` kept by decision. Publishing
      `lab/dev_test_input/*.yaml` discloses the names of the private `730alchemy/crodino`
      and `730alchemy/scratch` repos; accepted. `runs/` is gitignored with zero tracked
      files, so it was never a concern.
- [x] **10. `docs/` and `.claude/`** — reviewed; nothing internal-only left.
- [x] **11. Absolute local paths** — closed by removing `claude/`, the only source of
      `/home/markn/...` paths.

## Remaining

- [ ] **19. Verify a clean clone builds and tests green** — no reliance on the local
      `.venv` or `.env`.
- [ ] **20. Add a CI workflow** — Archipelago has none. Agent Foundry's `ci.yml` is
      a usable template. Open question: `addopts` pins `-n 8`, which oversubscribes a
      2–4 core runner; decide whether to override in CI.
- [ ] **21. SHA-pin `pdm-project/setup-pdm@v4`** in Agent Foundry's `ci.yml`.
- [ ] **7. GitHub protections** (after publish) — secret scanning + push protection,
      Dependabot, branch protection on `main`.

## Notes

- Historical references to `730alchemy` in `docs/archive/` and `docs/run-reports/`
  were left intact deliberately: those runs really did target `730alchemy/agent-foundry`
  at the time, and rewriting them would falsify the record.
- Findings from `project-check-2026-04-29.md` that outlived the publication work were
  filed as issues #43–#51 before the file was deleted.
