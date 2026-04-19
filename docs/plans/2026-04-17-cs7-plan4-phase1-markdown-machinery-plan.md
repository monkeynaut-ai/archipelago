# CS7 Plan 4 — Phase 1: Declarative Markdown-Document Machinery (Agent Foundry) — Implementation Plan

> **Status:** Design draft. Pending review before Phase-1 implementation begins.
> **Date:** 2026-04-17
> **Roadmap:** `docs/plans/2026-04-03-review-feedback-loop-roadmap.md` (CS7 Plan 4)
> **Parent plan:** `docs/plans/2026-04-17-cs7-plan4-archipelago-agents-plan.md`
> **Architectural ADR:** `agent-foundry/docs/architecture/adr_markdown_template_model_shape.md`
> **Cross-repo:** all Phase-1 work lives in **agent-foundry**; archipelago is the eventual consumer but is not touched in Phase 1.

## Where this plan fits

CS7 Plan 4 covers the four Archipelago agents (Reviewer, Planner, Integrator, Dispatcher) and two `FunctionAction`s (CommitAction, SubmitPRAction). The brainstorm on 2026-04-17 produced the framing decision that **the inter-agent communication substrate is workspace-mediated markdown documents whose templates are Pydantic models** (see ADR), and the construction tier for the platform is **Tier 1 — schema-aware instructions**. Implementing this requires building the platform machinery first.

This plan covers **Phase 1 of CS7 Plan 4: the platform machinery in Agent Foundry**. Subsequent phases will:

- **Phase 2** (anticipated) — extend the machinery (instruction-appendix generation, `to_claude_code_schema` integration for shared schemas, semantic validation, additional annotation types).
- **Phase 3+** — implement the four Archipelago agents and two function actions on the platform machinery.

Phase 1 is **agent-foundry-only**. Nothing in archipelago is modified in this phase.

---

## Goal

**Build the minimum platform machinery in Agent Foundry that lets an application declare a Pydantic model representing a markdown-document template, and then have the platform — without further application code — render the template, parse a produced document into a populated model instance, and extract subtrees of a document by heading.**

After Phase 1, an application can:

```python
from agent_foundry.markdown import MarkdownDocument, AsHeading, AsList, render_template, validate_markdown, extract_subtree

class Finding(MarkdownDocument):
    title: Annotated[str, AsHeading(text_template="Finding {ordinal} - {value}")]
    rationale: Annotated[str, AsHeading()]
    suggested_fix: Annotated[str, AsHeading()]

class Review(MarkdownDocument):
    title: Annotated[str, AsHeading()]
    summary: Annotated[str, AsHeading()]
    findings: Annotated[list[Finding], AsList()]

template_md = render_template(Review)              # generates the annotated skeleton
review = validate_markdown(produced_md, Review)    # parses + validates → Review instance
fragment = extract_subtree(produced_md, heading_level=3, title_match="Finding 1")
parsed_finding = validate_markdown(fragment, Finding)
```

Zero validation code is written by the application.

---

## Architecture

The machinery is organized as a small package, `agent_foundry.markdown`, with three layers:

1. **Element model layer** — typed Pydantic classes for the markdown elements we care about (`MarkdownHeading`, `MarkdownCodeBlock`, `MarkdownTable`, `MarkdownBulletList`, `MarkdownNumberedList`, `MarkdownFrontmatter`), unified by a `kind`-discriminated union. These are the runtime intermediate representation between the markdown AST and the application's domain model.
2. **Annotation + base-class layer** — annotation classes (`AsHeading`, `AsList`, `AsCodeBlock`, `AsTable`, `AsBulletList`, `AsNumberedList`, `AsFrontmatter`) carried on domain fields via `Annotated[T, ...]`. A base class `MarkdownDocument(BaseModel)` triggers structural meta-validation at class-definition time.
3. **Engine layer** — three engines that operate on the above: `render_template`, `validate_markdown` (parse + validate → instance), and `extract_subtree` (AST-level lookup primitive). All three are stateless functions; no global state.

The pipeline for parsing/validation:

```
markdown text → markdown-it-py AST → element tree (typed Pydantic union) → annotation-driven projector → populated domain model instance
```

The pipeline for rendering:

```
populated domain model instance → annotation-driven walker → element tree → markdown text
```

Subtree extraction operates one level lower — directly on the AST — so the same lookup mechanism works whether the caller wants to validate the result or just inspect it.

---

## Tech Stack

- Python 3.13+ (matches Agent Foundry's existing baseline; archipelago is 3.14)
- Pydantic v2 (already a project dependency)
- `markdown-it-py` (new dependency; pure-Python CommonMark + GFM AST parser, well-maintained)
- pytest with pytest-xdist for the test suite

No new runtime dependencies beyond `markdown-it-py`. No LLM calls, no I/O, no Docker.

---

## Scope

### In scope (Phase 1)

**Element model layer**

- Six element classes:
  - `MarkdownHeading(text, body)` — recursive (body may contain nested `MarkdownHeading` and other elements).
  - `MarkdownCodeBlock(language, content)`.
  - `MarkdownTable(columns, rows)`.
  - `MarkdownBulletList(items)` — items are plain inline strings (no nested lists in Phase 1).
  - `MarkdownNumberedList(items)` — same.
  - `MarkdownFrontmatter(data)` — `data` is a typed Pydantic sub-model.
- A `MarkdownKind` `StrEnum` carrying the discriminator values.
- A `BlockElement` discriminated union of every element class except `MarkdownFrontmatter` (frontmatter is document-root-only).

**Annotation layer**

- Annotation classes:
  - `AsHeading(text_template: str | None = None)` — the **only constraint annotation in Phase 1**. The `text_template` may use `{value}` (the field's stringified value) and `{ordinal}` (1-based index when used inside an `AsList`). When `text_template` is `None`, the heading text is derived from the field name (snake_case → Title Case). No `level` parameter — level is always inferred from nesting depth at render time.
  - `AsList()` — for `list[BaseModel]` fields. The wrapper heading text is derived from the field name (or supplied via `text="..."`); each item is rendered as a sub-document under its own heading at the next level. Item-heading text and constraints come from the `AsHeading` annotation on the item-model's first field.
  - `AsCodeBlock(language: str | None = None)` — for `str` fields. Field value becomes the code-block content; `language` becomes the fence language tag.
  - `AsTable()` — for `list[BaseModel]` fields where the inner model has only scalar fields. Columns are derived from the inner model's field names; each list item becomes one row.
  - `AsBulletList()` — for `list[str]` fields.
  - `AsNumberedList()` — for `list[str]` fields.
  - `AsFrontmatter()` — for a single `BaseModel` field that is the **first field** of the top-level `MarkdownDocument` subclass. The field type is the typed schema for the YAML body.

**Base class + meta-validation**

- `MarkdownDocument(BaseModel)` — base class for top-level document templates.
- A `__pydantic_init_subclass__` hook that runs the structural meta-validator on the subclass at definition time.
- Meta-validation rules enforced (errors raised at class definition):
  1. **Order rule** — within any container model (the document itself or a nested `BaseModel`), no scope-absorbed element field may follow a heading-introducing element field. Heading-introducing = `AsHeading` (when the field type is `BaseModel` or `list[BaseModel]`) and `AsList`. Scope-absorbed = `AsCodeBlock`, `AsTable`, `AsBulletList`, `AsNumberedList`, and `AsHeading` on a leaf string field where the body is plain text. The validator distinguishes leaf vs. container by inspecting the annotated type.
  2. **Frontmatter rule** — `AsFrontmatter` may appear only as the first field of a top-level `MarkdownDocument` subclass; never on a nested model, never on a non-first field.
  3. **Type-annotation compatibility rule** — every annotation has an allowed set of underlying types (e.g., `AsCodeBlock` only on `str`, `AsTable` only on `list[BaseModel]` with scalar inner fields, `AsBulletList` only on `list[str]`). Mismatches raise at class definition.
- The meta-validator never runs on plain `BaseModel` subclasses (only on `MarkdownDocument` and its descendants), so the rest of Agent Foundry / Archipelago is unaffected.

**Engines**

- `render_template(model_class: type[MarkdownDocument]) -> str` — renders the **annotated skeleton** the agent will mimic: every heading is emitted with its derived text, every body region is filled with placeholder text that includes the field's `Field(description=...)` as a comment.
- `render_instance(instance: MarkdownDocument) -> str` — renders a populated model instance to markdown text. Used by tests and (later) by upstream agents producing inputs for downstream agents.
- `validate_markdown(markdown: str, model_class: type[MarkdownDocument]) -> MarkdownDocument` — parses the markdown, validates against the model, and returns a populated instance. Raises a `MarkdownValidationError` with field-localized diagnostics on failure.
- `extract_subtree(markdown: str, *, heading_level: int, title_match: str) -> str` — returns the subtree (as a markdown string) under the heading at the given level whose title matches `title_match`. The matching rule for `title_match` is **exact string equality** in Phase 1 (regex/template support deferred). Returns the heading and its scoped body, with heading levels rebased so the matched heading becomes level 1 in the returned text — making the result directly validatable against a model whose top-level field is at level 1.

**Behaviors**

- **Strict order matching** — model field order must match document order. A reordered document fails validation with a clear "expected `## Goal` before `## Findings`, found them reversed" message.
- **Passthrough of unmodeled content** — markdown content that does not correspond to any model field is permitted but ignored. Free prose between modeled elements, untyped headings, etc., do not cause validation errors. Only the modeled elements are required to be present, in order, and conforming.
- **Semantic equivalence on round-trip** — `parse(render(instance))` must yield an equivalent instance (`==` on the Pydantic model). Byte-identity is **not** required.

### Out of scope for Phase 1

- `MarkdownSection` (dropped during brainstorm — headings cover the same shapes more reliably).
- `MarkdownParagraph` (dropped — every modeled element must have an explicit identity; standalone prose is passthrough).
- Heading-level override (level is always inferred; no `AsHeading(level=N)`).
- Instruction-appendix generation (Phase 2).
- `to_claude_code_schema` integration so the same model can drive both markdown round-trip and JSON-schema emission for `--json-schema` (Phase 2).
- Semantic (LLM-checked) validation of field contents against descriptions (Phase 2 or later).
- Annotations beyond the seven listed above (deferred until concrete need).
- Nested lists, rich list items, multi-paragraph table cells, GFM extensions beyond tables (deferred).
- Round-trip byte-identity (we target semantic equivalence only).
- Streaming/incremental parsing (deferred).
- Anything in archipelago.

---

## Locked design decisions (carried from the 2026-04-17 brainstorm)

These are non-negotiable for Phase 1; revising any of them requires re-entering the brainstorm.

1. **Element classes use a `kind` discriminator** (per project convention; required because the AST → normalized JSON → Pydantic chain passes through JSON).
2. **Annotated domain models, not pure-structure models** (Option iii from the ADR). Application authors write domain Pydantic types and annotate fields; they do not reference `MarkdownHeading` or other element classes directly.
3. **Heading level is inferred from nesting depth** at render time. No `level` parameter on `AsHeading`. No `level` field on `MarkdownHeading` (the element class) — level is an AST concern, used only by `extract_subtree`, and disappears once an element instance is constructed.
4. **Strongly typed everywhere unless utterly impossible.** Frontmatter content is a typed `BaseModel`, not `dict[str, Any]`. Table rows are typed `BaseModel`s, not `list[Any]`. List items are typed.
5. **Meta-validation runs at class-definition time** via `MarkdownDocument.__pydantic_init_subclass__`. No user invocation; no opt-in beyond inheriting from `MarkdownDocument`.
6. **Strict order matching.** Model field order = document order. Reordered documents fail validation.
7. **Unmodeled content passes through** the validator without error.
8. **Validation returns a populated model instance** (option (b) from the brainstorm), not just a pass/fail.
9. **Subtree extractor is a Phase 1 deliverable** so function actions consuming markdown documents have the full toolkit on day one.

---

## Detailed design

### 1. Element classes

All element classes are concrete `BaseModel` subclasses with a `kind` field as the discriminator.

```python
from enum import StrEnum
from typing import Annotated, Literal
from pydantic import BaseModel, Field

class MarkdownKind(StrEnum):
    HEADING = "heading"
    CODE_BLOCK = "code_block"
    TABLE = "table"
    BULLET_LIST = "bullet_list"
    NUMBERED_LIST = "numbered_list"
    FRONTMATTER = "frontmatter"

class MarkdownHeading(BaseModel):
    kind: Literal[MarkdownKind.HEADING] = MarkdownKind.HEADING
    text: str
    body: list["BlockElement"] = Field(default_factory=list)

class MarkdownCodeBlock(BaseModel):
    kind: Literal[MarkdownKind.CODE_BLOCK] = MarkdownKind.CODE_BLOCK
    language: str | None = None
    content: str

class MarkdownTableRow(BaseModel):
    cells: list[str]

class MarkdownTable(BaseModel):
    kind: Literal[MarkdownKind.TABLE] = MarkdownKind.TABLE
    columns: list[str]
    rows: list[MarkdownTableRow]

class MarkdownBulletList(BaseModel):
    kind: Literal[MarkdownKind.BULLET_LIST] = MarkdownKind.BULLET_LIST
    items: list[str]

class MarkdownNumberedList(BaseModel):
    kind: Literal[MarkdownKind.NUMBERED_LIST] = MarkdownKind.NUMBERED_LIST
    items: list[str]

class MarkdownFrontmatter(BaseModel):
    kind: Literal[MarkdownKind.FRONTMATTER] = MarkdownKind.FRONTMATTER
    data: BaseModel  # the typed schema for the YAML body; concrete type set per use site

BlockElement = Annotated[
    MarkdownHeading
    | MarkdownCodeBlock
    | MarkdownTable
    | MarkdownBulletList
    | MarkdownNumberedList,
    Field(discriminator="kind"),
]

# Resolve forward reference for recursive heading bodies
MarkdownHeading.model_rebuild()
```

Notes:
- `MarkdownFrontmatter` is excluded from `BlockElement` because it can only appear at the document root.
- `MarkdownHeading.body` is `list[BlockElement]` — recursive nesting via `BlockElement` (which itself includes `MarkdownHeading`).
- Element classes are mostly internal — application authors generally do not import them directly.

### 2. Annotation classes

Annotations are plain Python objects (not Pydantic models). They carry per-field configuration that the engine layer reads at runtime via `model_fields[name].metadata`.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class AsHeading:
    """Render the field as a heading; field value is the heading's body."""
    text_template: str | None = None
    # text_template placeholders: {value}, {ordinal}
    # When None, heading text derives from the field name (snake_case → Title Case)

@dataclass(frozen=True)
class AsList:
    """Render a list[BaseModel] field as a wrapper heading + per-item sub-headings."""
    text: str | None = None
    # When None, wrapper heading text derives from the field name

@dataclass(frozen=True)
class AsCodeBlock:
    """Render a str field as a fenced code block."""
    language: str | None = None

@dataclass(frozen=True)
class AsTable:
    """Render a list[BaseModel] field as a table; columns derived from inner model fields."""
    pass

@dataclass(frozen=True)
class AsBulletList:
    """Render a list[str] field as a bullet list."""
    pass

@dataclass(frozen=True)
class AsNumberedList:
    """Render a list[str] field as a numbered list."""
    pass

@dataclass(frozen=True)
class AsFrontmatter:
    """Render a single BaseModel field as YAML frontmatter. Document-root-only, first-field-only."""
    pass
```

These are deliberately small. Each is a marker that pairs an underlying Pydantic field type with a rendering / parsing rule. Future phases will add fields to existing annotations and introduce new ones.

### 3. Annotation ↔ field-type compatibility matrix

Enforced by the meta-validator at class definition time:

| Annotation | Allowed field type | Notes |
|---|---|---|
| `AsHeading` | `str` | Body is one plain-text paragraph (may contain `\n\n` for multi-paragraph). Heading text from template/field name. |
| `AsHeading` | `BaseModel` (subclass of `MarkdownDocument`) | Body is the rendered sub-model. Heading text from field name. |
| `AsList` | `list[BaseModel]` (item is a `MarkdownDocument` subclass) | Item-heading text from `AsHeading` annotation on item model's first field. |
| `AsCodeBlock` | `str` | Content is the field value. |
| `AsTable` | `list[BaseModel]` (item has only scalar fields) | Columns from item model's field names. |
| `AsBulletList` | `list[str]` | |
| `AsNumberedList` | `list[str]` | |
| `AsFrontmatter` | `BaseModel` | Must be first field of a top-level `MarkdownDocument`. |

### 4. `MarkdownDocument` base class + meta-validation

```python
class MarkdownDocument(BaseModel):
    """Base class for any Pydantic model that represents a markdown document template
    or a sub-document used inside one. Triggers structural meta-validation at class
    definition time."""

    def __pydantic_init_subclass__(cls, **kwargs):
        super().__pydantic_init_subclass__(**kwargs)
        from agent_foundry.markdown.meta_validation import validate_template_class
        validate_template_class(cls)
```

`validate_template_class(cls)` walks `cls.model_fields` and enforces the meta-validation rules. It raises `MarkdownTemplateError` (a subclass of `TypeError`) at definition time if any rule is violated. Errors include the offending field name, the rule violated, and a concrete fix suggestion.

Example error message for the order rule:

```
MarkdownTemplateError: in Review.findings, field type list[Finding] with AsList annotation
is heading-introducing, but Review.summary_table (AsTable) is scope-absorbed and follows it.
Reorder Review's fields so all scope-absorbed fields (table/list/code-block/scalar-heading)
precede heading-introducing fields (AsList, AsHeading on a BaseModel/list[BaseModel]).
```

### 5. Renderer

`render_template(model_class)` produces the annotated skeleton — an empty document the agent sees as part of its instructions.

`render_instance(instance)` produces a populated document.

Both walk the model's fields in declaration order, dispatch on each field's annotation, and emit the corresponding markdown. The current heading depth is tracked as a parameter; nested `BaseModel` fields recurse with depth + 1.

Implementation sketch:

```python
def render_instance(instance: MarkdownDocument, *, heading_level: int = 1) -> str:
    parts: list[str] = []
    for name, field in type(instance).model_fields.items():
        ann = _get_annotation(field)
        value = getattr(instance, name)
        parts.append(_render_field(name, field, ann, value, heading_level))
    return "\n\n".join(parts).rstrip() + "\n"
```

Each annotation has a corresponding `_render_field_*` handler in the engine. The renderer is **deterministic**: the same instance always produces the same markdown bytes. This is useful for tests and for the round-trip property check.

### 6. Parser / validator

`validate_markdown(markdown, model_class)` runs the four-stage pipeline:

1. **Markdown → AST** via `markdown-it-py` with the GFM table plugin.
2. **AST → element tree** — a small normalizer that walks the AST and produces a tree of typed `BlockElement` instances (plus an optional `MarkdownFrontmatter` at the top).
3. **Element tree → projection onto domain model** — the annotation-driven projector walks `model_class.model_fields` in declaration order, locates the corresponding subtree(s) in the element tree by annotation rule, extracts field values, and constructs a kwargs dict.
4. **Pydantic instantiation + standard validation** — `model_class(**kwargs)`. Pydantic's standard validation runs (type coercion, required fields, etc.).

Errors at any stage raise `MarkdownValidationError`, a subclass of `pydantic.ValidationError`-style structured error carrying:
- The model class
- The offending field path (e.g., `Review.findings[2].title`)
- The offending annotation
- The expected pattern
- The actual content
- A suggested fix

These errors are designed to be folded into the in-loop correction prompt that Plan 2 set up for `AgentFilePath` — Phase 2 will wire that integration.

### 7. Subtree extractor

```python
def extract_subtree(
    markdown: str,
    *,
    heading_level: int,
    title_match: str,
) -> str:
    ...
```

Operates on the AST directly:

1. Parse markdown to AST.
2. Walk the AST top-down, looking for a heading node whose level equals `heading_level` and whose text equals `title_match` (exact string match in Phase 1).
3. Find that heading's scope (everything until the next heading at level ≤ `heading_level`).
4. Rebase heading levels: the matched heading becomes level 1, descendant headings shift by the same delta.
5. Render the rebased subtree back to markdown text.

The returned string is then passable to `validate_markdown(returned, SomeModelClass)` for typed inspection.

If no matching heading is found, raises `MarkdownExtractionError`. If multiple match, raises with a clear message.

### 8. Module layout

```
agent-foundry/src/agent_foundry/markdown/
├── __init__.py             # public API exports
├── annotations.py          # AsHeading, AsList, AsCodeBlock, AsTable, AsBulletList, AsNumberedList, AsFrontmatter
├── elements.py             # MarkdownKind, element classes, BlockElement
├── template_model.py       # MarkdownDocument base class
├── meta_validation.py      # validate_template_class + meta-validation rules
├── renderer.py             # render_template, render_instance, per-annotation handlers
├── parser.py               # validate_markdown, AST normalizer, projector
├── extractor.py            # extract_subtree
└── errors.py               # MarkdownTemplateError, MarkdownValidationError, MarkdownExtractionError
```

Public API surface (everything reachable from `agent_foundry.markdown`):

```python
from agent_foundry.markdown import (
    # Base class + annotations
    MarkdownDocument,
    AsHeading, AsList, AsCodeBlock, AsTable, AsBulletList, AsNumberedList, AsFrontmatter,
    # Engines
    render_template, render_instance, validate_markdown, extract_subtree,
    # Errors
    MarkdownTemplateError, MarkdownValidationError, MarkdownExtractionError,
)
```

Element classes are NOT exported by default — they are internal interchange types. Importable from `agent_foundry.markdown.elements` for advanced cases (tests, debugging).

### 9. Test approach

TDD per project convention. Test layout mirrors source layout.

```
agent-foundry/tests/agent_foundry/markdown/
├── test_elements.py         # construction + serialization of element classes
├── test_annotations.py      # annotation construction + introspection
├── test_template_model.py   # MarkdownDocument inheritance behavior
├── test_meta_validation.py  # all meta-rule violations + valid templates
├── test_renderer.py         # render_template and render_instance behavior per annotation
├── test_parser.py           # validate_markdown happy paths + each error class
├── test_extractor.py        # extract_subtree happy paths + edge cases (no match, multi match)
├── test_round_trip.py       # property tests: parse(render(instance)) == instance
└── fixtures/                # canonical markdown documents the parser must handle
    ├── review_simple.md
    ├── review_with_findings.md
    └── review_with_passthrough.md
```

**Round-trip property tests** are the most powerful coverage: for each test model, generate instances (hand-written or via Hypothesis), render, parse, assert equivalence. Catches both renderer and parser bugs in one shot.

---

## Tasks (TDD; checkbox-tracked)

Each task: tests first, then implementation. Mark `- [x]` as completed.

### Phase 1.1 — Element model and annotations (foundation)

- [ ] **1.1.1** Tests for element classes (`test_elements.py`) — construction, serialization, deserialization, discriminator round-trip.
- [ ] **1.1.2** `agent_foundry/markdown/elements.py` — `MarkdownKind` enum, all six element classes, `BlockElement` discriminated union, `MarkdownHeading.model_rebuild()`.
- [ ] **1.1.3** Tests for annotation classes (`test_annotations.py`) — construction, equality, frozen-dataclass behavior.
- [ ] **1.1.4** `agent_foundry/markdown/annotations.py` — all seven annotation dataclasses.
- [ ] **1.1.5** Tests for error types (in `test_meta_validation.py`, `test_parser.py`, `test_extractor.py` headers).
- [ ] **1.1.6** `agent_foundry/markdown/errors.py` — `MarkdownTemplateError`, `MarkdownValidationError`, `MarkdownExtractionError`.

### Phase 1.2 — `MarkdownDocument` + meta-validation

- [ ] **1.2.1** Tests for `MarkdownDocument` inheritance (`test_template_model.py`) — confirms `__pydantic_init_subclass__` fires.
- [ ] **1.2.2** `agent_foundry/markdown/template_model.py` — `MarkdownDocument` base class with `__pydantic_init_subclass__` hook.
- [ ] **1.2.3** Tests for meta-validation (`test_meta_validation.py`) — every rule, valid and invalid examples for each, error messages asserted to contain the offending field name and rule.
- [ ] **1.2.4** `agent_foundry/markdown/meta_validation.py` — `validate_template_class(cls)` implementing:
  - [ ] Order rule
  - [ ] Frontmatter rule
  - [ ] Type-annotation compatibility rule

### Phase 1.3 — Renderer

- [ ] **1.3.1** Tests for `render_template` skeleton output (`test_renderer.py`) — one test per annotation type, asserting the skeleton structure.
- [ ] **1.3.2** Tests for `render_instance` populated output — one per annotation, plus a multi-field composite.
- [ ] **1.3.3** `agent_foundry/markdown/renderer.py` — `render_template`, `render_instance`, per-annotation handlers, heading-level inference.

### Phase 1.4 — Parser / validator

- [ ] **1.4.1** Add `markdown-it-py` to `pyproject.toml`.
- [ ] **1.4.2** Tests for AST normalizer — feed it canonical markdown fixtures, assert the produced element tree.
- [ ] **1.4.3** AST normalizer in `parser.py`.
- [ ] **1.4.4** Tests for the projector (element tree → domain model) — happy path per annotation, plus order-violation failure messages.
- [ ] **1.4.5** Projector in `parser.py`.
- [ ] **1.4.6** `validate_markdown` glue function.
- [ ] **1.4.7** Tests for passthrough behavior — markdown with extra unmodeled headings/prose still validates if modeled elements are present in order.

### Phase 1.5 — Subtree extractor

- [ ] **1.5.1** Tests for `extract_subtree` — happy paths, no match, multiple match, level-rebasing correctness.
- [ ] **1.5.2** `agent_foundry/markdown/extractor.py`.
- [ ] **1.5.3** Integration test: extract → validate against a sub-model.

### Phase 1.6 — Round-trip property tests

- [ ] **1.6.1** `test_round_trip.py` with hand-written instances of every Phase-1-shape covered.
- [ ] **1.6.2** (Optional) Hypothesis-based property tests for fuzzing.

### Phase 1.7 — Public API + docs

- [ ] **1.7.1** `agent_foundry/markdown/__init__.py` exports.
- [ ] **1.7.2** Module-level docstrings + a short usage example in the package `__init__`.
- [ ] **1.7.3** Update `agent-foundry/docs/architecture/adr_markdown_template_model_shape.md` "Status" to reflect that Phase 1 is implemented (after this plan ships).

---

## Open questions for the implementer

These do not block writing this plan but will surface during implementation. Resolve at the relevant task; document the resolution in the source.

- **AST → element-tree fidelity for tables.** GFM tables in `markdown-it-py` produce nested inline content per cell; we need to flatten to plain `str` for `MarkdownTableRow.cells` (Phase 1 doesn't support rich cell content). Document the flattening rule in `parser.py` docstring.
- **Heading-text matching when `text_template` contains a placeholder.** For `AsHeading(text_template="Finding {ordinal} - {value}")`, the parser must reverse the template: locate headings matching the literal portions, extract `{value}` and `{ordinal}` (and verify ordinal correctness). Implementation will likely use a simple state-machine or a regex compiled from the template.
- **Disambiguating `AsHeading` on a `str` field with multi-paragraph body.** A heading body for a `str` field can contain blank lines, which represent paragraph breaks. The parser concatenates paragraphs with `\n\n` to reconstitute the field value. Confirm this is the intended round-trip semantics.
- **Recursive class definitions and `model_rebuild()`.** When a `MarkdownDocument` subclass nests another `MarkdownDocument` subclass, the meta-validator must run after Pydantic resolves forward references. May require deferring meta-validation to the first time the class is "ready," not strictly at `__pydantic_init_subclass__`. Confirm during implementation.
- **`extract_subtree` and frontmatter.** If a document has frontmatter and the extracted subtree starts deeper, the extracted text won't include the frontmatter. Document this behavior; if a use case demands extracted-with-frontmatter, add a parameter later.

---

## Verification (Phase 1 done)

- [ ] `pdm test-unit` passes in agent-foundry with all new tests.
- [ ] All meta-validation rules raise on bad templates and pass on good ones.
- [ ] Round-trip property tests pass for every annotation type.
- [ ] At least one end-to-end example: define `Review` and `Finding` template classes, render, parse, extract a finding subtree, re-validate. Documented in `tests/agent_foundry/markdown/test_round_trip.py` or as an `examples/` script.
- [ ] No new lint or typecheck errors. Pyright strict on the new module.
- [ ] Public API surface matches the documented exports; nothing else is reachable from `agent_foundry.markdown`.

## Change log

- **2026-04-17** — Plan drafted, captures the brainstorm decisions from CS7 Plan 4 design session and the architectural ADR.
