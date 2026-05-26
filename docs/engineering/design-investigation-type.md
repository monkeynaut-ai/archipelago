# Typing the Designer Investigation Summary

**Status:** Deferred (2026-05-26). Captured for future work.
**Origin:** Surfaced while planning design review (`docs/plans/2026-05-26-design-review-plan.md`); the plan currently loads the investigation summary as raw text.

## The question

The Designer emits two artifacts: a `DesignDocument` and an *investigation summary*. The design document is a fully structured `MarkdownDocument` (typed `AsHeading` sections, Pydantic-validated). The investigation summary is **freeform markdown with no schema** — the Designer instructions template only asks it to write "what you learned, what's still uncertain" to `investigation.md`.

The design-review work needs the quality reviewer to consume the investigation summary as codebase context. The approved design (`docs/plans/2026-05-24-design-review-design.md`, "New Components" → `load_investigation_into_state`) loads it as a raw `str` and embeds it in the reviewer prompt as a fenced code block, justifying this as:

> "The investigation summary is freeform Designer output with no canonical schema, so loading it as raw text avoids inventing a Pydantic model just to round-trip text the reviewer reads in full anyway."

## Why the raw-text choice is weak

1. **It violates a stated project convention.** `CLAUDE.md` (Data Model Conventions): *"Every boundary type is a Pydantic `BaseModel` — runtime validation, schema generation, JSON round-trip. Plain dataclasses only for internal, non-serialized types."* The investigation summary crosses the Designer→reviewer boundary; it is exactly the kind of artifact the rule targets. The design doc's justification optimizes for the reviewer's reading convenience and sets the convention aside.

2. **There is no schema to lose, only one to introduce.** The artifact is unstructured *today* because nothing has modeled it yet — not because it resists structure. The Designer already produces a structured `DesignDocument`; a structured investigation summary is consistent with how the Designer already works, not a new burden in kind.

3. **It forces a redundant helper into existence.** Raw-text loading requires a new `read_workspace_file` helper in `workspace_io.py` that exists only because the artifact is unparsed. If the artifact were modeled, the existing `read_markdown(handle, path, Model)` would load it and no new helper would be needed.

4. **No validation of Designer output.** Raw text means a truncated, empty, or malformed investigation passes silently into the reviewer prompt. A typed model would fail loudly at the load boundary (as `read_markdown` already does for the design document).

## Recommendation

Introduce `InvestigationSummary(MarkdownDocument)`, mirroring `DesignDocument`. Proposed section set (drawn from what the Designer template currently asks it to investigate — "package structure, public interfaces and conventions, established patterns, test conventions"):

```python
class InvestigationSummary(MarkdownDocument):
    frontmatter: InvestigationSummaryFrontmatter | None = None
    title: Annotated[str, TextTemplate("Investigation for {value}")]
    scope_investigated: Annotated[str, AsHeading()]    # which areas/packages examined, and why
    relevant_components: Annotated[str, AsHeading()]    # existing modules/interfaces this feature touches
    established_patterns: Annotated[str, AsHeading()]   # conventions/patterns for similar concerns
    test_conventions: Annotated[str, AsHeading()]       # fixtures, test patterns available
    integration_points: Annotated[str, AsHeading()]     # upstream producers / downstream consumers
    open_uncertainties: Annotated[str, AsHeading()]     # what is still unknown
```

The exact section schema is itself a design choice worth a short brainstorm before implementation — it dictates what the Designer is *compelled* to report. The set above is a starting point, not a settled contract.

## Ripple effects (scope of the future change)

1. **New model** — `src/archipelago/models/investigation_summary.py` + export from `models/__init__.py`.
2. **Designer instructions template** (`src/archipelago/agents/designer/instructions_template.md`) — replace the freeform "investigation checkpoint" instruction with `render_template(InvestigationSummary)`, the same mechanism the template already uses for `DesignDocument`.
3. **Load action** — `load_investigation_into_state` parses via `read_markdown(..., InvestigationSummary)` and writes `investigation_summary: InvestigationSummary` instead of `investigation_summary_text: str`. The `read_workspace_file` helper is deleted (no longer needed once the artifact is typed).
4. **State + reviewer input** — `DesignReviewInput.investigation_summary: InvestigationSummary` (replacing `investigation_summary_text: str`); the quality reviewer prompt renders it via `render_instance` rather than embedding raw text in a code block. Update `DesignReviewState` / `FullPipelineState` field accordingly.

## Cost / counter-argument

Structuring the investigation imposes named sections on what has been the Designer's scratchpad. The design document already distills codebase findings into its own `current_state_context` section, so the raw investigation is partly a working note. The mitigating point: the Designer already fills a structured `DesignDocument`, so a structured investigation is in keeping with its existing output discipline rather than a new class of obligation. If a section genuinely doesn't apply, the Designer can write "none" with reasoning, as it already does for design-document sections.

## Decision

Deferred 2026-05-26. The design-review v1 plan proceeds with raw-text loading (`investigation_summary_text: str`, `read_workspace_file` helper). Revisit when modeling the investigation summary is prioritized — ideally as a small standalone brainstorm to settle the section schema, then a plan covering the four ripple points above.
