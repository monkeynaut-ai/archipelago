# CS7 Plan 4 — Phase 1: Declarative Markdown-Document Machinery (Agent Foundry) — Implementation Plan

> **Status:** Design draft, second iteration. Survived two sanity-check passes against the change-set Reviewer model. Pending final review before Phase-1 implementation begins.
> **Date:** 2026-04-17 (initial draft); revised same day after design sharpening
> **Roadmap:** `docs/plans/stage1/2026-04-03-review-feedback-loop-roadmap.md` (CS7 Plan 4)
> **Parent plan:** `docs/plans/stage1/2026-04-17-cs7-plan4-archipelago-agents-plan.md`
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
from typing import Annotated
from pydantic import BaseModel
from agent_foundry.markdown import (
    MarkdownDocument, MarkdownHeader,
    AsHeading, TextTemplate,
    render_template, validate_markdown, extract_subtree,
)

class ReviewMetadata(BaseModel):
    change_set_name: str
    commit_range: str

class Finding(MarkdownHeader):
    title: Annotated[str, TextTemplate("Finding {ordinal} - {value}")]
    description: Annotated[str, AsHeading()]
    rationale: Annotated[str, AsHeading()]
    suggested_fix: Annotated[str, AsHeading()]

class Review(MarkdownDocument):
    frontmatter: ReviewMetadata | None = None
    title: Annotated[str, TextTemplate("{value}")]
    summary: Annotated[str, AsHeading()]
    findings: list[Finding]

template_md = render_template(Review)              # generates the annotated skeleton
review = validate_markdown(produced_md, Review)    # parses + validates → Review instance
fragment = extract_subtree(produced_md, heading_level=3, title_match="Finding 1 - missing tests")
parsed_finding = validate_markdown(fragment, Finding)
```

Zero validation code is written by the application.

---

## Architecture

The machinery is organized as a small package, `agent_foundry.markdown`, with three layers:

1. **Element model layer** — typed Pydantic classes for the markdown elements we care about (`MarkdownHeading`, `MarkdownCodeBlock`, `MarkdownTable`, `MarkdownBulletList`, `MarkdownNumberedList`, `MarkdownFrontmatter`), unified by a `kind`-discriminated union. These are the runtime intermediate representation between the markdown AST and the application's domain model.
2. **Annotation + base-class layer** — two base classes (`MarkdownHeader` and `MarkdownDocument(MarkdownHeader)`) and a small annotation library (`AsHeading`, `AsCodeBlock`, `AsTable`, `AsBulletList`, `AsNumberedList`, `TextTemplate`) carried on domain fields via `Annotated[T, ...]`. The base classes trigger structural meta-validation at class-definition time via `__pydantic_init_subclass__`.
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

Six annotations. `AsList` and `AsFrontmatter` from the original draft are gone — list semantics are inferred from the field type, and frontmatter is a fixed-name field on `MarkdownDocument`.

- `AsHeading()` — for a `str` body field. Renders as a heading; field value becomes the heading body (free markdown text). Heading text is the field name (snake_case → Title Case). No parameters.
- `AsCodeBlock(language: str | None = None)` — for a `str` body field. Field value becomes the code-block content; `language` becomes the fence language tag.
- `AsTable()` — for a `list[BaseModel]` body field where the inner model has only scalar fields. Columns are derived from the inner model's field names; each list item becomes one row.
- `AsBulletList()` — for a `list[str]` body field.
- `AsNumberedList()` — for a `list[str]` body field.
- `TextTemplate("...")` — for heading-text fields. Two contexts:
  - On a `MarkdownHeader.title` field (str), the template formats the heading text. Placeholders: `{value}` (the field's value) and `{ordinal}` (1-based index when the parent is a list).
  - On a heading-introducing list-wrapper field (`list[MarkdownHeader-subclass]`), the template is a literal that overrides the default field-name-derived wrapper text. Placeholders do not apply (the field value is a list, not a formattable string).

**Base classes + meta-validation**

Two base classes, both inheriting from `pydantic.BaseModel`:

- `MarkdownHeader(BaseModel)` — base class for any heading-shaped sub-document. Declares a required `title: str` field. The `title` is structurally distinct: it carries the container's heading text. Body fields are everything else.
- `MarkdownDocument(MarkdownHeader)` — base class for top-level documents. Adds an optional `frontmatter: BaseModel | None = None` field that subclasses override with their specific frontmatter schema. Subclasses must declare `frontmatter` (if at all) as the first field. The renderer always emits frontmatter at the very top of the document, before the title heading.

Both base classes register a `__pydantic_init_subclass__` hook that runs the structural meta-validator on the subclass at definition time.

Meta-validation rules (errors raised at class definition):

1. **Title rule** — every `MarkdownHeader` subclass must have `title: str` as a field. (Inherited automatically; this rule catches accidental override-to-non-string-type.)
2. **Body order rule** — within a `MarkdownHeader` subclass's body (every field except `title`, plus on `MarkdownDocument` except `frontmatter`), all non-heading fields must precede all heading-introducing fields. Heading-introducing body fields: `Annotated[str, AsHeading()]`, fields typed as a `MarkdownHeader` subclass, fields typed `list[MarkdownHeader-subclass]`. Non-heading body fields: `AsCodeBlock`, `AsTable`, `AsBulletList`, `AsNumberedList`.
3. **Frontmatter rule** — only `MarkdownDocument` subclasses may declare a `frontmatter` field. If declared, it must be the first field of the subclass and its type must be `BaseModel | None` (a concrete `BaseModel` subclass union with `None`).
4. **Type-annotation compatibility rule** — every annotation has an allowed set of underlying types: `AsHeading` on `str`; `AsCodeBlock` on `str`; `AsTable` on `list[BaseModel]` with scalar inner fields; `AsBulletList`/`AsNumberedList` on `list[str]`; `TextTemplate` on `str` (title field) or any heading-introducing list wrapper. Mismatches raise at class definition.

The meta-validator never runs on plain `BaseModel` subclasses (only on `MarkdownHeader` and its descendants), so the rest of Agent Foundry / Archipelago is unaffected.

**Engines**

- `render_template(model_class: type[MarkdownHeader]) -> str` — renders the **annotated skeleton** the agent will mimic: every heading is emitted with its derived text, every body region is filled with placeholder text that includes the field's `Field(description=...)` as a comment. Accepts any `MarkdownHeader` subclass (including `MarkdownDocument` subclasses).
- `render_instance(instance: MarkdownHeader) -> str` — renders a populated model instance to markdown text. Used by tests and (later) by upstream agents producing inputs for downstream agents.
- `validate_markdown(markdown: str, model_class: type[MarkdownHeader]) -> MarkdownHeader` — parses the markdown, validates against the model, and returns a populated instance. Raises a `MarkdownValidationError` with field-localized diagnostics on failure.
- `extract_subtree(markdown: str, *, heading_level: int, title_match: str) -> str` — returns the subtree (as a markdown string) under the heading at the given level whose title matches `title_match`. The matching rule for `title_match` is **exact string equality** in Phase 1 (regex/template support deferred). Returns the heading and its scoped body, with heading levels rebased so the matched heading becomes level 1 in the returned text — making the result directly validatable against a model whose top-level field is at level 1.

**Heading-level inference (the rule that drives rendering)**

Each rendering context has a **current level**.

- The top-level model passed to `render_*` has current level = 1.
- A `MarkdownHeader.title` renders at the current level. The header's body has current level = title's level + 1.
- A heading-introducing body field (`AsHeading`-on-str, a nested `MarkdownHeader`, or a list of `MarkdownHeader`) renders its heading at the parent's body level.
- A `list[MarkdownHeader-subclass]` renders a wrapper heading at the body level; each item has current level = wrapper level + 1.
- **Render-time guard**: if any heading would emit at level > 6 (markdown maximum), the renderer raises a clear error naming the model and field path. This check cannot be done at class-definition time because depth depends on usage context.

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
3. **Two base classes: `MarkdownHeader` (with required `title: str`) and `MarkdownDocument(MarkdownHeader)` (with overridable `frontmatter` field).** The `title` field is a structural slot, not an annotated body field — its role as the container's heading is declared by the base class, not by an annotation. The two-class split serves one concrete purpose: only `MarkdownDocument` subclasses may declare frontmatter, enforced at class-definition time by the meta-validator.
4. **`AsList` does not exist** (and is not needed). A field typed `list[MarkdownHeader-subclass]` is self-declarative — the platform infers "wrapper heading + per-item sub-headings + ordinal counter" from the type alone. Only `list[str]` and `list[BaseModel-with-scalars]` need an annotation to disambiguate (`AsBulletList`/`AsNumberedList` vs. `AsTable`).
5. **`AsFrontmatter` does not exist.** The `frontmatter` field on `MarkdownDocument` is special by name (fixed) and by base-class declaration; no annotation needed.
6. **`TextTemplate("...")` is the single annotation for heading-text formatting.** Two contexts: on a `MarkdownHeader.title` field (placeholders `{value}` and `{ordinal}` apply), and on a heading-introducing list-wrapper field (literal-only override of the default field-name-derived wrapper text).
7. **Heading level is inferred from rendering context** (see "Heading-level inference" subsection). No `level` parameter on any annotation. No `level` field on `MarkdownHeading` (the element class) — level is an AST concern, used only by `extract_subtree`, and disappears once an element instance is constructed.
8. **Strongly typed everywhere unless utterly impossible.** Frontmatter content is a typed `BaseModel`, not `dict[str, Any]`. Table rows are typed `BaseModel`s, not `list[Any]`. List items are typed.
9. **Meta-validation runs at class-definition time** via `MarkdownHeader.__pydantic_init_subclass__`. No user invocation; no opt-in beyond inheriting from `MarkdownHeader` or `MarkdownDocument`.
10. **Strict order matching.** Model field order = document order. Reordered documents fail validation.
11. **Unmodeled content passes through** the validator without error. Inside an `Annotated[str, AsHeading()]` body, *all* content is unmodeled — the value is captured as raw markdown text within the heading's scope.
12. **Validation returns a populated model instance** (option (b) from the brainstorm), not just a pass/fail.
13. **Subtree extractor is a Phase 1 deliverable** so function actions consuming markdown documents have the full toolkit on day one.

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
    raw_yaml: str   # the raw YAML text inside the --- fences
    parsed: dict   # the YAML parsed into a dict; the projector validates this against the model's frontmatter field type

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
- Element classes are mostly internal — application authors generally do not import them directly. They interact with the platform through `MarkdownHeader`, `MarkdownDocument`, and the annotation library.

### 2. Annotation classes

Annotations are plain Python objects (not Pydantic models). They carry per-field configuration that the engine layer reads at runtime via `model_fields[name].metadata`. Six annotations total.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class AsHeading:
    """Render a str body field as a heading whose body is the field value (raw markdown text).
    Heading text is derived from the field name (snake_case → Title Case)."""
    pass  # no parameters; field name determines heading text

@dataclass(frozen=True)
class AsCodeBlock:
    """Render a str body field as a fenced code block."""
    language: str | None = None

@dataclass(frozen=True)
class AsTable:
    """Render a list[BaseModel] body field as a table; columns derived from inner model fields."""
    pass

@dataclass(frozen=True)
class AsBulletList:
    """Render a list[str] body field as a bullet list."""
    pass

@dataclass(frozen=True)
class AsNumberedList:
    """Render a list[str] body field as a numbered list."""
    pass

@dataclass(frozen=True)
class TextTemplate:
    """Format a heading-text field using a template.

    Two contexts:
      - On a MarkdownHeader.title field (str): {value} substitutes the field value;
        {ordinal} substitutes the 1-based list index when the parent is a list.
      - On a heading-introducing list-wrapper field (list[MarkdownHeader-subclass]):
        the template is a literal that overrides the default field-name-derived
        wrapper text. Placeholders do not apply (field value is a list).
    """
    template: str
```

These are deliberately small. Each is a marker that pairs an underlying Pydantic field type with a rendering / parsing rule. Future phases will add fields to existing annotations and introduce new ones.

### 3. Field shapes and what each declares

Authors mostly declare body fields using one of these shapes. The meta-validator enforces the type constraints at class-definition time.

| Field shape | Renders as | Where it can appear |
|---|---|---|
| `Annotated[str, AsHeading()]` | `## <field name>` heading + the str value as raw markdown body | Body field of any `MarkdownHeader` |
| `Annotated[str, AsCodeBlock(language=...)]` | Fenced code block with the str value as content | Non-heading body field |
| `Annotated[list[BaseModel-with-scalars], AsTable()]` | Markdown table; columns from inner model field names | Non-heading body field |
| `Annotated[list[str], AsBulletList()]` | Bullet list | Non-heading body field |
| `Annotated[list[str], AsNumberedList()]` | Numbered list | Non-heading body field |
| `<SomeMarkdownHeaderSubclass>` (no annotation) | The instance's title becomes the heading; its body renders below | Heading-introducing body field |
| `list[<SomeMarkdownHeaderSubclass>]` (no annotation) | Wrapper heading (text from field name) + each item rendered as a sub-heading at wrapper level + 1; ordinal counter available to item title templates | Heading-introducing body field |

**Special structural fields (declared by base classes, not by annotations):**

| Field | Declared by | Renders as |
|---|---|---|
| `title: str` | `MarkdownHeader` | The container's heading text (level inferred from context). Required on every `MarkdownHeader` subclass. May be overridden in a subclass with `Annotated[str, TextTemplate("...")]` to apply a template. |
| `frontmatter: BaseModel \| None = None` | `MarkdownDocument` | YAML frontmatter at the very top of the document. Optional — defaults to `None`, in which case nothing is rendered. Subclasses may override the type with a more specific `BaseModel` schema. Must be the first declared field on subclasses that override it. |

### 4. `MarkdownHeader` and `MarkdownDocument` base classes + meta-validation

```python
class MarkdownHeader(BaseModel):
    """Base class for any heading-shaped sub-document.

    Declares a required `title: str` field that carries the container's heading text.
    Body fields are everything else. Body field order is constrained:
    non-heading fields must precede heading-introducing fields.
    """

    title: str  # required; the container's heading text

    def __pydantic_init_subclass__(cls, **kwargs):
        super().__pydantic_init_subclass__(**kwargs)
        from agent_foundry.markdown.meta_validation import validate_template_class
        validate_template_class(cls)


class MarkdownDocument(MarkdownHeader):
    """Base class for top-level markdown documents.

    Adds an optional `frontmatter: BaseModel | None = None` field. Subclasses
    may override this with a more specific BaseModel schema. The renderer
    always emits frontmatter at the top of the document, before the title heading.
    """

    frontmatter: BaseModel | None = None  # subclasses override the BaseModel type
```

`validate_template_class(cls)` walks `cls.model_fields` and enforces the meta-validation rules. It raises `MarkdownTemplateError` (a subclass of `TypeError`) at definition time if any rule is violated. Errors include the offending field name, the rule violated, and a concrete fix suggestion.

Example error message for the body order rule:

```
MarkdownTemplateError: in Finding, field 'code_snippet' (Annotated[str, AsCodeBlock])
is non-heading and follows field 'description' (Annotated[str, AsHeading()]) which is
heading-introducing. Within a MarkdownHeader subclass's body, all non-heading fields
must precede all heading-introducing fields. Reorder so 'code_snippet' comes before
'description', or move it into 'description''s body.
```

Example error message for the frontmatter rule:

```
MarkdownTemplateError: in NestedFinding, field 'frontmatter' is declared, but
NestedFinding inherits from MarkdownHeader (not MarkdownDocument). Frontmatter
is allowed only on MarkdownDocument subclasses. Either change the base class to
MarkdownDocument, or remove the frontmatter field.
```

### 5. Renderer

`render_template(model_class)` produces the annotated skeleton — an empty document the agent sees as part of its instructions.

`render_instance(instance)` produces a populated document.

Both walk the model's fields in declaration order, dispatch on each field's role (structural — `title`, `frontmatter` — or annotation-driven), and emit the corresponding markdown. The current heading level is tracked as a parameter; nested `MarkdownHeader` subclasses recurse with the appropriate level shift (see "Heading-level inference" subsection above).

Implementation sketch:

```python
def render_instance(instance: MarkdownHeader, *, current_level: int = 1) -> str:
    parts: list[str] = []

    # 1. Frontmatter (only on MarkdownDocument subclasses with frontmatter set)
    if isinstance(instance, MarkdownDocument) and instance.frontmatter is not None:
        parts.append(_render_frontmatter(instance.frontmatter))

    # 2. Title heading at current_level
    parts.append(_render_title(instance, current_level))

    # 3. Body fields in declaration order, at current_level + 1
    for name, field in type(instance).model_fields.items():
        if name in ("title", "frontmatter"):
            continue
        value = getattr(instance, name)
        parts.append(_render_body_field(name, field, value, current_level + 1))

    return "\n\n".join(p for p in parts if p).rstrip() + "\n"
```

Each field shape (annotated body field, structural title, structural frontmatter) has its own handler. The renderer is **deterministic**: the same instance always produces the same markdown bytes. This is useful for tests and for the round-trip property check.

**Heading-depth guard.** Before emitting any heading, the renderer checks that the level is ≤ 6. If a level-7+ heading would be emitted, it raises with the model class and field path so the author can shorten the nesting.

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
├── annotations.py          # AsHeading, AsCodeBlock, AsTable, AsBulletList, AsNumberedList, TextTemplate
├── elements.py             # MarkdownKind, element classes, BlockElement
├── template_model.py       # MarkdownHeader and MarkdownDocument base classes
├── meta_validation.py      # validate_template_class + meta-validation rules
├── renderer.py             # render_template, render_instance, per-field-shape handlers
├── parser.py               # validate_markdown, AST normalizer, projector
├── extractor.py            # extract_subtree
└── errors.py               # MarkdownTemplateError, MarkdownValidationError, MarkdownExtractionError
```

Public API surface (everything reachable from `agent_foundry.markdown`):

```python
from agent_foundry.markdown import (
    # Base classes + annotations
    MarkdownHeader, MarkdownDocument,
    AsHeading, AsCodeBlock, AsTable, AsBulletList, AsNumberedList, TextTemplate,
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
├── test_template_model.py   # MarkdownHeader and MarkdownDocument inheritance behavior
├── test_meta_validation.py  # all meta-rule violations + valid templates
├── test_renderer.py         # render_template and render_instance behavior per field shape
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
- [ ] **1.1.4** `agent_foundry/markdown/annotations.py` — six annotation dataclasses (`AsHeading`, `AsCodeBlock`, `AsTable`, `AsBulletList`, `AsNumberedList`, `TextTemplate`).
- [ ] **1.1.5** Tests for error types (in `test_meta_validation.py`, `test_parser.py`, `test_extractor.py` headers).
- [ ] **1.1.6** `agent_foundry/markdown/errors.py` — `MarkdownTemplateError`, `MarkdownValidationError`, `MarkdownExtractionError`.

### Phase 1.2 — `MarkdownHeader`, `MarkdownDocument`, meta-validation

- [ ] **1.2.1** Tests for `MarkdownHeader` and `MarkdownDocument` inheritance (`test_template_model.py`) — `title` is required on `MarkdownHeader` subclasses; `frontmatter` field is overridable on `MarkdownDocument` subclasses; `__pydantic_init_subclass__` fires on both.
- [ ] **1.2.2** `agent_foundry/markdown/template_model.py` — `MarkdownHeader` base class (with required `title: str` and the meta-validation hook); `MarkdownDocument(MarkdownHeader)` adding `frontmatter: BaseModel | None = None`.
- [ ] **1.2.3** Tests for meta-validation (`test_meta_validation.py`) — every rule with valid and invalid examples; error messages asserted to contain the offending field name and rule.
- [ ] **1.2.4** `agent_foundry/markdown/meta_validation.py` — `validate_template_class(cls)` implementing:
  - [ ] Title rule (`title: str` required on every `MarkdownHeader` subclass; not overridden to a non-string type)
  - [ ] Body order rule (non-heading body fields must precede heading-introducing body fields; `title` and `frontmatter` are exempt structural fields)
  - [ ] Frontmatter rule (only `MarkdownDocument` subclasses; first declared field; type is `BaseModel | None`)
  - [ ] Type-annotation compatibility rule (every annotation has an allowed underlying type; mismatches raise)

### Phase 1.3 — Renderer

- [ ] **1.3.1** Tests for `render_template` skeleton output (`test_renderer.py`) — one test per field shape, asserting the skeleton structure.
- [ ] **1.3.2** Tests for `render_instance` populated output — one per field shape, plus a multi-field composite (the change-set Reviewer model from the sanity-check is a good fixture).
- [ ] **1.3.3** Tests for `TextTemplate` substitution — `{value}` and `{ordinal}` on a `MarkdownHeader.title`; literal-only on a list-wrapper.
- [ ] **1.3.4** Tests for the heading-depth-6 render-time guard.
- [ ] **1.3.5** `agent_foundry/markdown/renderer.py` — `render_template`, `render_instance`, per-field-shape handlers, heading-level inference, depth-6 guard.

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
- **Heading-text matching when `TextTemplate` contains a placeholder.** For `TextTemplate("Finding {ordinal} - {value}")`, the parser must reverse the template: locate headings matching the literal portions, extract `{value}` and `{ordinal}` (and verify ordinal correctness). Implementation will likely use a simple state-machine or a regex compiled from the template.
- **`AsHeading` on a `str` body with rich content.** The body of a `str` field annotated `AsHeading()` is captured as raw markdown text within the heading's scope (paragraphs, lists, code blocks, even sub-headings — anything goes). Confirm the parser preserves whitespace/formatting cleanly enough that round-trip equivalence holds for typical agent output.
- **Recursive class definitions and `model_rebuild()`.** When a `MarkdownHeader` subclass nests another `MarkdownHeader` subclass, the meta-validator must run after Pydantic resolves forward references. May require deferring meta-validation to the first time the class is "ready," not strictly at `__pydantic_init_subclass__`. Confirm during implementation.
- **`extract_subtree` and frontmatter.** If a document has frontmatter and the extracted subtree starts deeper, the extracted text won't include the frontmatter. Document this behavior; if a use case demands extracted-with-frontmatter, add a parameter later.
- **Single `MarkdownHeader`-typed body field heading text.** For a body field whose type is a single `MarkdownHeader` subclass (no list), the heading text comes from the *instance's* `title` value, not the field name. Document this behavior so authors don't expect field-name-derived text in this case. (Cleanest workaround when field-name semantics are wanted: use `Annotated[str, AsHeading()]` instead of a sub-`MarkdownHeader`.)

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
- **2026-04-17** — **Major design revision** following sanity-check #2. Replaces `MarkdownDocument`-only base with two base classes (`MarkdownHeader` and `MarkdownDocument(MarkdownHeader)`). Removes `AsList` (list semantics inferred from type) and `AsFrontmatter` (`frontmatter` is a fixed-name field on `MarkdownDocument`). Adds `TextTemplate` annotation for heading-text formatting (replaces `AsHeading(text_template=...)`). Sharpens body-order rule (applies only within body fields, not relative to title or frontmatter). Documents heading-level inference rule explicitly. Adds render-time guard for heading depth > 6.
