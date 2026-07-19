# Security Policy

## Supported versions

Archipelago is pre-1.0 and under active development. Security fixes are applied to the
`main` branch. There are no long-term support branches.

## Reporting a vulnerability

Please do **not** open a public issue for security vulnerabilities.

Report privately through one of these channels:

1. **GitHub private vulnerability reporting** (preferred) — open a report from the
   repository's **Security → Report a vulnerability** tab. This keeps the discussion
   private until a fix is ready.
2. **Email** — security@monkeynaut.ai

Please include:

- A description of the vulnerability and its impact.
- Steps to reproduce, or a proof of concept.
- Affected components, versions, or commit hashes.
- Any suggested remediation, if you have one.

## What to expect

- **Acknowledgement** within 3 business days.
- **Initial assessment** of severity and scope within 7 business days.
- **Coordinated disclosure** — we will work with you on a fix and a disclosure
  timeline, and credit you in the release notes unless you prefer to remain anonymous.

## Threat model — what counts as a vulnerability

Archipelago runs LLM-authored code against a real repository. Some behavior that looks
alarming is the documented design, and some is a genuine defect. The line:

**In scope**

- Credential leakage — auth tokens reaching logs, run artifacts, telemetry, committed
  files, or any surface outside the intended env allowlist.
- Container escape, or agent-authored code reaching host resources not deliberately
  mounted into the workspace.
- Privilege widening — a run touching repositories, branches, or services beyond the
  target it was given.
- Prompt injection from repository content (source files, issues, PR bodies) that
  causes an agent to exfiltrate secrets or act outside its declared task.

**Out of scope — documented behavior, not a defect**

- Agents write code, run commands, commit, and open pull requests in the target
  repository. That is the product.
- Agent containers have network access to the model provider and GitHub.
- The token you supply determines the blast radius. A broadly scoped `GITHUB_TOKEN`
  granting broad access is your configuration, not a vulnerability — see the Safety
  section of the [README](README.md).

Thank you for helping keep Archipelago and its users safe.
