# CS7 Plan 4 Phase 1 — Markdown Machinery Implementation Plan

> **Status:** Revised 2026-04-17 after jig:review swarm (5 blocking + 4 major findings addressed in this version).
> **Design:** `docs/plans/stage1/2026-04-17-cs7-plan4-phase1-markdown-machinery-design.md`
> **ADR:** `agent-foundry/docs/architecture/adr_markdown_template_model_shape.md`
> **Parent:** `docs/plans/stage1/2026-04-17-cs7-plan4-archipelago-agents-plan.md`
> **For agents:** Use team-dev (parallel) or sdd (sequential) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the declarative markdown-document machinery in agent-foundry — six element classes, six annotations, two base classes with class-definition-time meta-validation, a deterministic renderer, a parser/validator that returns populated Pydantic instances, and a heading-keyed subtree extractor — so applications declare ordinary Pydantic templates and Agent Foundry handles all rendering, parsing, and validation with zero application code.

**Architecture:** Three layers in `agent_foundry.markdown`. Element classes form a `kind`-discriminated union representing the parser's intermediate form. Annotations attach via `Annotated[T, ...]` to fields on `MarkdownHeader` / `MarkdownDocument` subclasses; meta-validation fires at class-definition time via `__pydantic_init_subclass__`. Engines are stateless: `render_template`, `render_instance`, `validate_markdown`, `extract_subtree`.

**Tech Stack:** Python 3.14, Pydantic 2.12+, `markdown-it-py` (new dependency), pytest with pytest-xdist, ruff, pyright. All work in the **agent-foundry** repo (sibling at `../agent-foundry`); archipelago is unchanged.

---

## Repo orientation

All file paths in this plan are relative to the **agent-foundry** repo root (`../agent-foundry/` from this archipelago repo). Commit and run all commands inside that repo. Cross-repo plan; the plan document lives in archipelago for continuity with CS7's other plans.

```bash
cd /home/markn/engineering/jig-archipelago/agent-foundry
```

For brevity, the rest of this plan omits the `cd` and assumes commands run with that as the working directory.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `pyproject.toml` | Modify | Add `markdown-it-py` dependency |
| `src/agent_foundry/markdown/__init__.py` | Create | Public API exports |
| `src/agent_foundry/markdown/elements.py` | Create | `MarkdownKind` enum, **seven** element classes (six block-level + `MarkdownFrontmatter`), `BlockElement` discriminated union. **Note:** `MarkdownParagraph` is included as an internal AST element so the AST normalizer can round-trip prose content; it is not exposed via any annotation (authors never reference it directly). |
| `src/agent_foundry/markdown/annotations.py` | Create | Six annotation dataclasses (`AsHeading`, `AsCodeBlock`, `AsTable`, `AsBulletList`, `AsNumberedList`, `TextTemplate`) |
| `src/agent_foundry/markdown/errors.py` | Create | `MarkdownTemplateError`, `MarkdownValidationError`, `MarkdownExtractionError` |
| `src/agent_foundry/markdown/template_model.py` | Create | `MarkdownHeader` + `MarkdownDocument` base classes with meta-validation hook |
| `src/agent_foundry/markdown/meta_validation.py` | Create | `validate_template_class` + four meta-validation rules |
| `src/agent_foundry/markdown/renderer.py` | Create | `render_template`, `render_instance`, per-field-shape handlers, depth-6 guard |
| `src/agent_foundry/markdown/_ast_normalizer.py` | Create | `markdown-it-py` AST → `BlockElement` tree |
| `src/agent_foundry/markdown/_projector.py` | Create | Element tree → populated Pydantic instance (annotation-driven walker) |
| `src/agent_foundry/markdown/parser.py` | Create | `validate_markdown` glue function |
| `src/agent_foundry/markdown/extractor.py` | Create | `extract_subtree` AST-level lookup |
| `tests/agent_foundry/markdown/__init__.py` | Create | Empty test package marker |
| `tests/agent_foundry/markdown/test_elements.py` | Create | Element-class construction + serialization tests |
| `tests/agent_foundry/markdown/test_annotations.py` | Create | Annotation construction + introspection tests |
| `tests/agent_foundry/markdown/test_errors.py` | Create | Error-class hierarchy and message-formatting tests |
| `tests/agent_foundry/markdown/test_template_model.py` | Create | `MarkdownHeader` / `MarkdownDocument` base class tests |
| `tests/agent_foundry/markdown/test_meta_validation.py` | Create | Meta-validation rule tests (valid + invalid examples per rule) |
| `tests/agent_foundry/markdown/test_renderer.py` | Create | Renderer tests per field shape, `TextTemplate` substitution, depth-6 guard |
| `tests/agent_foundry/markdown/test_ast_normalizer.py` | Create | AST normalizer tests |
| `tests/agent_foundry/markdown/test_projector.py` | Create | Projector tests, strict-order matching, passthrough |
| `tests/agent_foundry/markdown/test_parser.py` | Create | `validate_markdown` end-to-end tests |
| `tests/agent_foundry/markdown/test_extractor.py` | Create | Subtree-extractor tests |
| `tests/agent_foundry/markdown/test_round_trip.py` | Create | Property tests: `parse(render(instance)) == instance` |
| `tests/agent_foundry/markdown/fixtures/__init__.py` | Create | Fixtures package marker |
| `tests/agent_foundry/markdown/fixtures/sample_models.py` | Create | Reusable test models (Reviewer, Finding, etc.) |

---

## Conventions

**Test naming:** classes named `Test<Feature>`, methods named `test_given_<context>_when_<action>_then_<expected>`. This matches the existing agent-foundry style (see `tests/agent_foundry/primitives/test_primitive_models.py`).

**Test commands** (run from agent-foundry repo root):
- Single test file: `pdm run pytest tests/agent_foundry/markdown/test_elements.py -xvs`
- Single test by name: `pdm run pytest tests/agent_foundry/markdown/test_elements.py::TestMarkdownHeading::test_given_text_when_constructed_then_kind_is_heading -xvs`
- All markdown tests: `pdm run pytest tests/agent_foundry/markdown/ -xvs`
- Full unit suite: `pdm test-unit`

**Lint and typecheck:**
- `pdm lint` — ruff check (auto-fix)
- `pdm format` — ruff format
- `pdm typecheck` — pyright strict

**Commit convention:** `feat(markdown): <message>` for code additions, `test(markdown): <message>` if a commit is purely test additions, `chore(markdown): <message>` for non-code (e.g., dependency add). Each commit ends with `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

**TDD discipline:** every task starts with a failing test. Run the test, confirm failure, then write minimum code to pass, then confirm pass, then commit. Never commit without all tests passing.

**Typecheck scope caveat:** `pdm typecheck` runs pyright over `src/` only (per `pyproject.toml [tool.pyright] include = ["src"]`). Test code — including the fixture models in `tests/agent_foundry/markdown/fixtures/sample_models.py` that exercise the application-side `Annotated[T, ...]` API — is **not** typechecked. Tests themselves are the validation for application-boundary correctness.

**Cross-repo lockfile note:** Adding `markdown-it-py` to agent-foundry's `pyproject.toml` does not automatically update archipelago's `pdm.lock` even though archipelago has a file-path dependency on agent-foundry. After the dependency add (Task 1.2.1), run `pdm install` from the archipelago repo to re-lock. The plan flags this in Task 1.2.1's steps.

---

## Phase 1.1 — Foundation: errors, elements, annotations

### Task 1.1.1: Create error hierarchy

**Files:**
- Create: `src/agent_foundry/markdown/__init__.py` (empty for now)
- Create: `src/agent_foundry/markdown/errors.py`
- Create: `tests/agent_foundry/markdown/__init__.py` (empty)
- Create: `tests/agent_foundry/markdown/test_errors.py`

**Dependencies:** None (foundation task).

- [ ] **Step 1: Create empty package directories**

```bash
mkdir -p src/agent_foundry/markdown
touch src/agent_foundry/markdown/__init__.py
mkdir -p tests/agent_foundry/markdown
touch tests/agent_foundry/markdown/__init__.py
```

- [ ] **Step 2: Write failing test**

Create `tests/agent_foundry/markdown/test_errors.py`:

```python
"""Tests for the markdown machinery error hierarchy."""

from __future__ import annotations

import pytest

from agent_foundry.markdown.errors import (
    MarkdownError,
    MarkdownExtractionError,
    MarkdownTemplateError,
    MarkdownValidationError,
)


class TestErrorHierarchy:
    """All markdown errors share a common base class for catch-all handling."""

    def test_template_error_is_markdown_error(self):
        with pytest.raises(MarkdownError):
            raise MarkdownTemplateError("template broke")

    def test_validation_error_is_markdown_error(self):
        with pytest.raises(MarkdownError):
            raise MarkdownValidationError("validation broke")

    def test_extraction_error_is_markdown_error(self):
        with pytest.raises(MarkdownError):
            raise MarkdownExtractionError("extraction broke")

    def test_template_error_is_type_error(self):
        """MarkdownTemplateError fires at class definition; behaves as a TypeError."""
        assert issubclass(MarkdownTemplateError, TypeError)


class TestErrorMessages:
    """Error messages preserve their content."""

    def test_template_error_preserves_message(self):
        err = MarkdownTemplateError("field X is invalid")
        assert "field X is invalid" in str(err)

    def test_validation_error_preserves_message(self):
        err = MarkdownValidationError("expected ## Goal, found ## Goals")
        assert "expected ## Goal" in str(err)
```

- [ ] **Step 3: Run test, confirm fails**

Run: `pdm run pytest tests/agent_foundry/markdown/test_errors.py -xvs`
Expected: `ModuleNotFoundError: No module named 'agent_foundry.markdown.errors'`

- [ ] **Step 4: Write minimal implementation**

Create `src/agent_foundry/markdown/errors.py`:

```python
"""Error hierarchy for the agent_foundry.markdown package."""

from __future__ import annotations


class MarkdownError(Exception):
    """Base class for all markdown machinery errors."""


class MarkdownTemplateError(MarkdownError, TypeError):
    """Raised at class-definition time when a MarkdownHeader/MarkdownDocument
    subclass violates a structural rule (title required, body order, frontmatter
    placement, type-annotation compatibility).

    Inherits from TypeError because the violation is a class-construction problem,
    not a runtime data problem.
    """


class MarkdownValidationError(MarkdownError):
    """Raised when a produced markdown document fails to validate against a
    template model (missing required heading, mismatched order, etc.)."""


class MarkdownExtractionError(MarkdownError):
    """Raised when extract_subtree cannot satisfy its lookup
    (no matching heading, multiple matches, etc.)."""
```

- [ ] **Step 5: Run test, confirm passes**

Run: `pdm run pytest tests/agent_foundry/markdown/test_errors.py -xvs`
Expected: 5 passed.

- [ ] **Step 6: Lint, format, typecheck**

Run: `pdm format && pdm lint && pdm typecheck`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add src/agent_foundry/markdown/__init__.py src/agent_foundry/markdown/errors.py tests/agent_foundry/markdown/__init__.py tests/agent_foundry/markdown/test_errors.py
git commit -m "$(cat <<'EOF'
feat(markdown): add error hierarchy for markdown machinery

Foundation for the declarative markdown-document machinery (CS7 Plan 4
Phase 1). MarkdownError is the catch-all base; MarkdownTemplateError
also subclasses TypeError because it fires at class-definition time.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.1.2: Element classes — `MarkdownKind`, `MarkdownHeading`

**Files:**
- Create: `src/agent_foundry/markdown/elements.py` (initial scaffold)
- Modify: `tests/agent_foundry/markdown/test_elements.py` (create new)

**Dependencies:** Task 1.1.1 (errors module exists).

- [ ] **Step 1: Write failing test**

Create `tests/agent_foundry/markdown/test_elements.py`:

```python
"""Tests for markdown element classes (parser intermediate representation)."""

from __future__ import annotations

import pytest

from agent_foundry.markdown.elements import MarkdownHeading, MarkdownKind


class TestMarkdownHeading:
    """MarkdownHeading represents a parsed markdown heading + its scope body."""

    def test_given_text_when_constructed_then_kind_is_heading(self):
        h = MarkdownHeading(text="Goal", body=[])
        assert h.kind == MarkdownKind.HEADING
        assert h.text == "Goal"
        assert h.body == []

    def test_given_no_body_when_constructed_then_body_defaults_to_empty(self):
        h = MarkdownHeading(text="Goal")
        assert h.body == []

    def test_kind_is_immutable_discriminator(self):
        """The kind field cannot be set to a non-HEADING value."""
        with pytest.raises(Exception):
            MarkdownHeading(kind="not_a_heading", text="Goal")  # type: ignore[arg-type]
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/agent_foundry/markdown/test_elements.py -xvs`
Expected: `ModuleNotFoundError: No module named 'agent_foundry.markdown.elements'`

- [ ] **Step 3: Write minimal implementation**

Create `src/agent_foundry/markdown/elements.py`:

```python
"""Markdown element classes — the parser's typed intermediate representation.

Application authors do not normally import these classes directly. They interact
with the platform through MarkdownHeader, MarkdownDocument, and the annotation
library. Element classes are exported only for advanced use (tests, debugging).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class MarkdownKind(StrEnum):
    """Discriminator values for the BlockElement union."""

    HEADING = "heading"
    CODE_BLOCK = "code_block"
    TABLE = "table"
    BULLET_LIST = "bullet_list"
    NUMBERED_LIST = "numbered_list"
    FRONTMATTER = "frontmatter"


class MarkdownHeading(BaseModel):
    """A parsed markdown heading and its scoped body content.

    `text` is the heading's title text (without the `#` prefix).
    `body` is everything inside the heading's scope, recursively parsed
    into `BlockElement` instances. Note: heading level is intentionally
    NOT carried on this element; level is an AST concern used only by
    the subtree extractor.
    """

    kind: Literal[MarkdownKind.HEADING] = MarkdownKind.HEADING
    text: str
    body: list["BlockElement"] = Field(default_factory=list)


# Forward-declared until other element classes are added.
BlockElement = Annotated[MarkdownHeading, Field(discriminator="kind")]

MarkdownHeading.model_rebuild()
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/agent_foundry/markdown/test_elements.py -xvs`
Expected: 3 passed.

- [ ] **Step 5: Lint, format, typecheck**

Run: `pdm format && pdm lint && pdm typecheck`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/elements.py tests/agent_foundry/markdown/test_elements.py
git commit -m "$(cat <<'EOF'
feat(markdown): add MarkdownKind enum and MarkdownHeading element

First element class for the declarative markdown machinery. Heading
carries text and recursive body but no level (level is an AST concern,
used only by the subtree extractor). BlockElement union starts with
just MarkdownHeading; expanded in subsequent commits.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.1.3: Element classes — `MarkdownCodeBlock`

**Files:**
- Modify: `src/agent_foundry/markdown/elements.py`
- Modify: `tests/agent_foundry/markdown/test_elements.py`

**Dependencies:** Task 1.1.2.

- [ ] **Step 1: Append failing test**

Append to `tests/agent_foundry/markdown/test_elements.py`:

```python
from agent_foundry.markdown.elements import MarkdownCodeBlock


class TestMarkdownCodeBlock:
    """MarkdownCodeBlock represents a fenced code block."""

    def test_given_language_and_content_when_constructed_then_fields_match(self):
        c = MarkdownCodeBlock(language="python", content="def foo(): pass")
        assert c.kind == MarkdownKind.CODE_BLOCK
        assert c.language == "python"
        assert c.content == "def foo(): pass"

    def test_given_no_language_when_constructed_then_language_is_none(self):
        c = MarkdownCodeBlock(content="raw text")
        assert c.language is None
```

Also update the `from agent_foundry.markdown.elements import ...` line at the top of the file to include `MarkdownCodeBlock`.

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/agent_foundry/markdown/test_elements.py::TestMarkdownCodeBlock -xvs`
Expected: `ImportError: cannot import name 'MarkdownCodeBlock'`

- [ ] **Step 3: Append implementation**

Append to `src/agent_foundry/markdown/elements.py`, before the `BlockElement` definition:

```python
class MarkdownCodeBlock(BaseModel):
    """A parsed fenced code block.

    `language` is the fence's language tag (e.g. 'python'); None when no
    language tag was present (`​` ``` ​` followed immediately by code).
    `content` is the raw text inside the fences.
    """

    kind: Literal[MarkdownKind.CODE_BLOCK] = MarkdownKind.CODE_BLOCK
    language: str | None = None
    content: str
```

Update `BlockElement` to include the new class:

```python
BlockElement = Annotated[
    MarkdownHeading | MarkdownCodeBlock,
    Field(discriminator="kind"),
]
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/agent_foundry/markdown/test_elements.py -xvs`
Expected: 5 passed (3 from heading + 2 from code block).

- [ ] **Step 5: Lint, format, typecheck**

Run: `pdm format && pdm lint && pdm typecheck`

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/elements.py tests/agent_foundry/markdown/test_elements.py
git commit -m "$(cat <<'EOF'
feat(markdown): add MarkdownCodeBlock element

Code-block element with optional language tag and raw content string.
Joins MarkdownHeading in the BlockElement discriminated union.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.1.4: Element classes — `MarkdownTable` + `MarkdownTableRow`

**Files:**
- Modify: `src/agent_foundry/markdown/elements.py`
- Modify: `tests/agent_foundry/markdown/test_elements.py`

**Dependencies:** Task 1.1.3.

- [ ] **Step 1: Append failing test**

Append to `tests/agent_foundry/markdown/test_elements.py`:

```python
from agent_foundry.markdown.elements import MarkdownTable, MarkdownTableRow


class TestMarkdownTable:
    """MarkdownTable represents a GFM-style markdown table."""

    def test_given_columns_and_rows_when_constructed_then_fields_match(self):
        t = MarkdownTable(
            columns=["Path", "Lines"],
            rows=[
                MarkdownTableRow(cells=["src/foo.py", "120"]),
                MarkdownTableRow(cells=["src/bar.py", "45"]),
            ],
        )
        assert t.kind == MarkdownKind.TABLE
        assert t.columns == ["Path", "Lines"]
        assert len(t.rows) == 2
        assert t.rows[0].cells == ["src/foo.py", "120"]

    def test_given_zero_rows_when_constructed_then_rows_is_empty(self):
        t = MarkdownTable(columns=["A", "B"], rows=[])
        assert t.rows == []
```

Update the import line accordingly.

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/agent_foundry/markdown/test_elements.py::TestMarkdownTable -xvs`
Expected: `ImportError: cannot import name 'MarkdownTable'`

- [ ] **Step 3: Append implementation**

Append to `src/agent_foundry/markdown/elements.py` before `BlockElement`:

```python
class MarkdownTableRow(BaseModel):
    """One row of a parsed markdown table. Cells are flat strings; rich
    inline content within cells is flattened to plain text in Phase 1."""

    cells: list[str]


class MarkdownTable(BaseModel):
    """A parsed GFM markdown table.

    `columns` are the header labels in column order.
    `rows` are the data rows; each row's cells must align with columns.
    """

    kind: Literal[MarkdownKind.TABLE] = MarkdownKind.TABLE
    columns: list[str]
    rows: list[MarkdownTableRow]
```

Extend `BlockElement`:

```python
BlockElement = Annotated[
    MarkdownHeading | MarkdownCodeBlock | MarkdownTable,
    Field(discriminator="kind"),
]
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/agent_foundry/markdown/test_elements.py -xvs`
Expected: 7 passed.

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/elements.py tests/agent_foundry/markdown/test_elements.py
git commit -m "$(cat <<'EOF'
feat(markdown): add MarkdownTable and MarkdownTableRow elements

GFM-style table element. Cells are flat strings (rich inline content
flattening rule documented; Phase 1 keeps cells as plain text).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.1.5: Element classes — `MarkdownBulletList`, `MarkdownNumberedList`

**Files:**
- Modify: `src/agent_foundry/markdown/elements.py`
- Modify: `tests/agent_foundry/markdown/test_elements.py`

**Dependencies:** Task 1.1.4.

- [ ] **Step 1: Append failing test**

```python
from agent_foundry.markdown.elements import (
    MarkdownBulletList,
    MarkdownNumberedList,
)


class TestMarkdownBulletList:
    def test_given_items_when_constructed_then_fields_match(self):
        bl = MarkdownBulletList(items=["alpha", "beta"])
        assert bl.kind == MarkdownKind.BULLET_LIST
        assert bl.items == ["alpha", "beta"]


class TestMarkdownNumberedList:
    def test_given_items_when_constructed_then_fields_match(self):
        nl = MarkdownNumberedList(items=["first", "second"])
        assert nl.kind == MarkdownKind.NUMBERED_LIST
        assert nl.items == ["first", "second"]
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/agent_foundry/markdown/test_elements.py::TestMarkdownBulletList tests/agent_foundry/markdown/test_elements.py::TestMarkdownNumberedList -xvs`
Expected: `ImportError`.

- [ ] **Step 3: Append implementation**

```python
class MarkdownBulletList(BaseModel):
    """A parsed unordered (bullet) list. Items are flat strings; nested lists
    are not supported in Phase 1."""

    kind: Literal[MarkdownKind.BULLET_LIST] = MarkdownKind.BULLET_LIST
    items: list[str]


class MarkdownNumberedList(BaseModel):
    """A parsed ordered (numbered) list. Items are flat strings; nested lists
    are not supported in Phase 1."""

    kind: Literal[MarkdownKind.NUMBERED_LIST] = MarkdownKind.NUMBERED_LIST
    items: list[str]
```

Extend `BlockElement`:

```python
BlockElement = Annotated[
    MarkdownHeading
    | MarkdownCodeBlock
    | MarkdownTable
    | MarkdownBulletList
    | MarkdownNumberedList,
    Field(discriminator="kind"),
]
```

- [ ] **Step 4: Run test, confirm passes** — `pdm run pytest tests/agent_foundry/markdown/test_elements.py -xvs` → 9 passed.

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/elements.py tests/agent_foundry/markdown/test_elements.py
git commit -m "$(cat <<'EOF'
feat(markdown): add MarkdownBulletList and MarkdownNumberedList elements

Both carry flat list[str] items. Nested lists deferred to a future phase.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.1.6: Element class — `MarkdownFrontmatter`

**Files:**
- Modify: `src/agent_foundry/markdown/elements.py`
- Modify: `tests/agent_foundry/markdown/test_elements.py`

**Dependencies:** Task 1.1.5.

- [ ] **Step 1: Append failing test**

```python
from agent_foundry.markdown.elements import MarkdownFrontmatter


class TestMarkdownFrontmatter:
    """Frontmatter is a document-root-only element; not part of BlockElement."""

    def test_given_raw_yaml_when_constructed_then_fields_match(self):
        fm = MarkdownFrontmatter(raw_yaml="key: value\n", parsed={"key": "value"})
        assert fm.kind == MarkdownKind.FRONTMATTER
        assert fm.raw_yaml == "key: value\n"
        assert fm.parsed == {"key": "value"}

    def test_frontmatter_not_in_block_element_union(self):
        """Frontmatter cannot appear inside a heading body."""
        from agent_foundry.markdown.elements import BlockElement
        from typing import get_args

        # The discriminated union should not include MarkdownFrontmatter.
        # We check by asserting that MarkdownFrontmatter cannot be the type
        # arg of the underlying Union (it is intentionally separate).
        union_args = get_args(get_args(BlockElement)[0])
        assert MarkdownFrontmatter not in union_args
```

- [ ] **Step 2: Run test, confirm fails** — `ImportError`.

- [ ] **Step 3: Append implementation**

Append to `elements.py` (after the lists, before `BlockElement`):

```python
class MarkdownFrontmatter(BaseModel):
    """A parsed YAML frontmatter block. Document-root-only — never appears
    inside a heading body (and is excluded from the BlockElement union).

    `raw_yaml` is the literal text between the opening and closing `---` fences.
    `parsed` is the YAML decoded into a dict; the projector then validates this
    dict against the model's `frontmatter` field type (a typed BaseModel).
    """

    kind: Literal[MarkdownKind.FRONTMATTER] = MarkdownKind.FRONTMATTER
    raw_yaml: str
    parsed: dict
```

- [ ] **Step 4: Run test, confirm passes** — 11 passed total.

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/elements.py tests/agent_foundry/markdown/test_elements.py
git commit -m "$(cat <<'EOF'
feat(markdown): add MarkdownFrontmatter element (root-only)

Carries raw YAML text and parsed dict. Excluded from BlockElement union
because frontmatter can only appear at the document root, never inside
a heading body.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.1.7: Element class — `MarkdownParagraph` (internal AST representation)

**Files:**
- Modify: `src/agent_foundry/markdown/elements.py`
- Modify: `tests/agent_foundry/markdown/test_elements.py`

**Dependencies:** Task 1.1.6.

**Why:** the AST normalizer (Task 1.4.1) needs to capture paragraph tokens emitted by `markdown-it-py` (the `paragraph_open / inline / paragraph_close` triple). Without a `MarkdownParagraph` element, prose content inside an `AsHeading`-on-`str` field's body is silently dropped during parsing. This element is **internal infrastructure** — the application never references it; no annotation maps to it; it doesn't appear in the public API. It exists so the projector can serialize prose back when reconstituting `AsHeading` body fields.

- [ ] **Step 1: Append failing test**

```python
from agent_foundry.markdown.elements import MarkdownParagraph


class TestMarkdownParagraph:
    """MarkdownParagraph captures a single paragraph of inline text. Internal
    AST representation; not addressable via any annotation."""

    def test_given_content_when_constructed_then_fields_match(self):
        p = MarkdownParagraph(content="Some prose.")
        assert p.kind == MarkdownKind.PARAGRAPH
        assert p.content == "Some prose."
```

- [ ] **Step 2: Run test, confirm fails** — `ImportError`.

- [ ] **Step 3: Append implementation**

Add to `src/agent_foundry/markdown/elements.py` — first add `PARAGRAPH = "paragraph"` to `MarkdownKind`, then:

```python
class MarkdownParagraph(BaseModel):
    """A parsed paragraph of inline text. Internal AST element used by the
    AST normalizer to preserve prose content inside heading bodies. Not
    referenced from any annotation; not part of the public API."""

    kind: Literal[MarkdownKind.PARAGRAPH] = MarkdownKind.PARAGRAPH
    content: str
```

Extend `BlockElement` to include `MarkdownParagraph`:

```python
BlockElement = Annotated[
    MarkdownHeading
    | MarkdownCodeBlock
    | MarkdownTable
    | MarkdownBulletList
    | MarkdownNumberedList
    | MarkdownParagraph,
    Field(discriminator="kind"),
]
```

- [ ] **Step 4: Run test, confirm passes**

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/elements.py tests/agent_foundry/markdown/test_elements.py
git commit -m "$(cat <<'EOF'
feat(markdown): add MarkdownParagraph internal element

Internal AST representation for prose paragraphs. Required by the AST
normalizer (Task 1.4.1) to preserve text content inside heading bodies.
Not addressable from the public annotation API — applications use
Annotated[str, AsHeading()] for labeled-prose body fields.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.1.8: Annotation classes (six)

**Files:**
- Create: `src/agent_foundry/markdown/annotations.py`
- Create: `tests/agent_foundry/markdown/test_annotations.py`

**Dependencies:** None (annotations are independent of element classes).

- [ ] **Step 1: Write failing test**

Create `tests/agent_foundry/markdown/test_annotations.py`:

```python
"""Tests for annotation dataclasses."""

from __future__ import annotations

import pytest

from agent_foundry.markdown.annotations import (
    AsBulletList,
    AsCodeBlock,
    AsHeading,
    AsNumberedList,
    AsTable,
    TextTemplate,
)


class TestAnnotationConstruction:
    """Each annotation is a frozen dataclass; constructable with valid args."""

    def test_as_heading_takes_no_args(self):
        h = AsHeading()
        assert h is not None

    def test_as_code_block_with_language(self):
        c = AsCodeBlock(language="python")
        assert c.language == "python"

    def test_as_code_block_without_language(self):
        c = AsCodeBlock()
        assert c.language is None

    def test_as_table_takes_no_args(self):
        AsTable()

    def test_as_bullet_list_takes_no_args(self):
        AsBulletList()

    def test_as_numbered_list_takes_no_args(self):
        AsNumberedList()

    def test_text_template_takes_template_string(self):
        t = TextTemplate("Finding {ordinal} - {value}")
        assert t.template == "Finding {ordinal} - {value}"

    def test_text_template_requires_template(self):
        with pytest.raises(TypeError):
            TextTemplate()  # type: ignore[call-arg]


class TestAnnotationImmutability:
    """All annotations are frozen dataclasses; instances are immutable and hashable."""

    def test_as_heading_is_hashable(self):
        hash(AsHeading())

    def test_text_template_equal_for_equal_template(self):
        a = TextTemplate("X")
        b = TextTemplate("X")
        assert a == b
        assert hash(a) == hash(b)

    def test_as_code_block_immutable(self):
        c = AsCodeBlock(language="python")
        with pytest.raises(Exception):
            c.language = "rust"  # type: ignore[misc]
```

- [ ] **Step 2: Run test, confirm fails** — `ModuleNotFoundError: agent_foundry.markdown.annotations`.

- [ ] **Step 3: Write implementation**

Create `src/agent_foundry/markdown/annotations.py`:

```python
"""Annotation dataclasses attached to template-model fields via Annotated[T, ...].

These are plain Python objects (not Pydantic models). Pydantic stores them on
fields; the renderer / parser / validator engines read them via
`model_fields[name].metadata` at runtime.

All annotations are frozen so they are hashable and can be used as dict keys
or set members. The dataclass `eq=True` (default) ensures equal-config
annotations compare equal, which simplifies testing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AsHeading:
    """Render a `str` body field as a heading whose body is the field value
    (raw markdown text). Heading text is derived from the field name
    (snake_case → Title Case). No parameters in Phase 1."""


@dataclass(frozen=True)
class AsCodeBlock:
    """Render a `str` body field as a fenced code block. `language` becomes
    the fence's language tag; None emits an unfenced-language code block."""

    language: str | None = None


@dataclass(frozen=True)
class AsTable:
    """Render a `list[BaseModel-with-scalars]` body field as a markdown table.
    Columns are derived from the inner model's field names (in declaration
    order); each list item becomes one row."""


@dataclass(frozen=True)
class AsBulletList:
    """Render a `list[str]` body field as a bullet list."""


@dataclass(frozen=True)
class AsNumberedList:
    """Render a `list[str]` body field as a numbered list."""


@dataclass(frozen=True)
class TextTemplate:
    """Format a heading-text field using a template.

    Two contexts:
      - On a `MarkdownHeader.title` field (str): `{value}` substitutes the
        field value; `{ordinal}` substitutes the 1-based list index when
        the parent is a list.
      - On a heading-introducing list-wrapper field (list[MarkdownHeader-subclass]):
        the template is a literal that overrides the default field-name-derived
        wrapper text. Placeholders do not apply (the field value is a list,
        not a formattable string).
    """

    template: str
```

- [ ] **Step 4: Run test, confirm passes** — 11 passed.

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/annotations.py tests/agent_foundry/markdown/test_annotations.py
git commit -m "$(cat <<'EOF'
feat(markdown): add six annotation dataclasses

AsHeading, AsCodeBlock, AsTable, AsBulletList, AsNumberedList, TextTemplate.
All frozen dataclasses; hashable; immutable. Carried on template-model
fields via Annotated[T, ...] and read by the engine layer at runtime.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 1.2 — Base classes and meta-validation

### Task 1.2.1: Add `markdown-it-py` dependency

**Files:** `pyproject.toml`, `pdm.lock` (agent-foundry); also archipelago `pdm.lock` re-locked.

**Dependencies:** None (independent prep task).

**Notes from review:**
- `markdown-it-py` is already present in agent-foundry's `pdm.lock` as a transitive dep (pulled by `rich`/etc.) under `groups = ["dev"]`. The `pdm add` will promote it to the `default` group; the lockfile diff will be smaller than expected.
- We will use `MarkdownIt("commonmark").enable("table")` in Tasks 1.4.1 and 1.5.1 — **not** `MarkdownIt("gfm-like")`. The `gfm-like` preset enables the linkify rule which requires `linkify-it-py` (not installed; would crash at parse time). CommonMark + the table plugin gives us GFM tables without the extra dependency.
- `pyyaml` (already declared in `[project] dependencies`) is also imported by the AST normalizer (Task 1.4.1) and renderer (Task 1.3.6) — no additional `pdm add` needed for YAML support.

- [ ] **Step 1: Add dependency**

Run: `pdm add markdown-it-py`

This adds `markdown-it-py` to the `[project] dependencies` list and updates `pdm.lock`. The lockfile entry's `groups` field changes from `["dev"]` to `["default", "dev"]`.

- [ ] **Step 2: Verify install**

Run: `pdm run python -c "import markdown_it; print(markdown_it.__version__)"`
Expected: prints version string (e.g., `4.0.0`), no error.

Run: `pdm run python -c "from markdown_it import MarkdownIt; MarkdownIt('commonmark').enable('table').parse('| a | b |\n|---|---|\n| 1 | 2 |')"`
Expected: no error (confirms table support works without linkify-it-py).

- [ ] **Step 3: Re-lock archipelago**

```bash
cd /home/markn/engineering/jig-archipelago/archipelago
pdm install
cd /home/markn/engineering/jig-archipelago/agent-foundry
```

Expected: archipelago's `pdm.lock` updates to reflect the new agent-foundry dependency. No version conflicts.

- [ ] **Step 4: Commit (agent-foundry)**

```bash
git add pyproject.toml pdm.lock
git commit -m "$(cat <<'EOF'
chore(markdown): add markdown-it-py dependency

Required by the AST normalizer (Phase 1.4) and subtree extractor
(Phase 1.5). Pure-Python CommonMark + GFM parser; no native code.
Already present transitively under "dev" group via rich; this promotes
it to the "default" group.

The implementation uses MarkdownIt("commonmark").enable("table") rather
than MarkdownIt("gfm-like") to avoid the linkify-it-py transitive
dependency that the gfm-like preset would require.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: Commit (archipelago)** — if `pdm.lock` changed, commit the update there too.

```bash
cd /home/markn/engineering/jig-archipelago/archipelago
git add pdm.lock
git commit -m "$(cat <<'EOF'
chore: re-lock for agent-foundry markdown-it-py addition

Archipelago depends on agent-foundry as a local file path; re-lock
to pick up the new transitive dependency.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
cd /home/markn/engineering/jig-archipelago/agent-foundry
```

---

### Task 1.2.2: `MarkdownHeader` base class (no meta-validation yet)

**Files:**
- Create: `src/agent_foundry/markdown/template_model.py`
- Create: `tests/agent_foundry/markdown/test_template_model.py`

**Dependencies:** Task 1.1.8.

- [ ] **Step 1: Write failing test**

Create `tests/agent_foundry/markdown/test_template_model.py`:

```python
"""Tests for MarkdownHeader and MarkdownDocument base classes."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from agent_foundry.markdown.template_model import MarkdownHeader


class TestMarkdownHeaderTitle:
    """MarkdownHeader requires a title field on every subclass."""

    def test_given_title_when_constructed_then_title_set(self):
        class SimpleHeader(MarkdownHeader):
            pass

        h = SimpleHeader(title="My Heading")
        assert h.title == "My Heading"

    def test_missing_title_raises_validation_error(self):
        class SimpleHeader(MarkdownHeader):
            pass

        with pytest.raises(ValidationError, match="title"):
            SimpleHeader()  # type: ignore[call-arg]

    def test_subclass_can_have_additional_fields(self):
        class WithBody(MarkdownHeader):
            description: str

        w = WithBody(title="X", description="Y")
        assert w.title == "X"
        assert w.description == "Y"
```

- [ ] **Step 2: Run test, confirm fails** — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Create `src/agent_foundry/markdown/template_model.py`:

```python
"""Base classes for markdown-document templates.

MarkdownHeader is the base for any heading-shaped sub-document; declares the
required `title: str` field. MarkdownDocument is the top-level base; adds
the optional `frontmatter` field. Both register a __pydantic_init_subclass__
hook (added in a later task) that runs structural meta-validation at
class-definition time.
"""

from __future__ import annotations

from pydantic import BaseModel


class MarkdownHeader(BaseModel):
    """Base class for any heading-shaped sub-document.

    Declares a required `title: str` field that carries the container's
    heading text. Body fields are everything except `title`. The body
    field-order rule (non-heading fields must precede heading-introducing
    fields) is enforced by the meta-validator.
    """

    title: str
```

- [ ] **Step 4: Run test, confirm passes** — 3 passed.

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/template_model.py tests/agent_foundry/markdown/test_template_model.py
git commit -m "$(cat <<'EOF'
feat(markdown): add MarkdownHeader base class with required title

First base class for the template-model layer. Declares title:str as
required; subclasses inherit and may add body fields. Meta-validation
hook is wired up in a later task.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.2.3: `MarkdownDocument` base class with `frontmatter` field

**Files:**
- Modify: `src/agent_foundry/markdown/template_model.py`
- Modify: `tests/agent_foundry/markdown/test_template_model.py`

**Dependencies:** Task 1.2.2.

- [ ] **Step 1: Append failing test**

```python
from agent_foundry.markdown.template_model import MarkdownDocument


class FrontmatterSchema(BaseModel):
    name: str
    version: int


class TestMarkdownDocument:
    """MarkdownDocument extends MarkdownHeader with an optional frontmatter field."""

    def test_inherits_title_from_markdown_header(self):
        class Doc(MarkdownDocument):
            pass

        d = Doc(title="hello")
        assert d.title == "hello"
        assert d.frontmatter is None

    def test_subclass_can_override_frontmatter_type(self):
        class Doc(MarkdownDocument):
            frontmatter: FrontmatterSchema | None = None

        d = Doc(title="hello", frontmatter=FrontmatterSchema(name="x", version=1))
        assert d.frontmatter is not None
        assert d.frontmatter.name == "x"

    def test_frontmatter_optional_default_none(self):
        class Doc(MarkdownDocument):
            frontmatter: FrontmatterSchema | None = None

        d = Doc(title="hello")
        assert d.frontmatter is None

    def test_markdown_document_is_markdown_header(self):
        from agent_foundry.markdown.template_model import MarkdownHeader

        assert issubclass(MarkdownDocument, MarkdownHeader)
```

- [ ] **Step 2: Run test, confirm fails** — `ImportError: cannot import name 'MarkdownDocument'`.

- [ ] **Step 3: Append implementation**

Append to `src/agent_foundry/markdown/template_model.py`:

```python
class MarkdownDocument(MarkdownHeader):
    """Base class for top-level markdown documents.

    Adds an optional `frontmatter: BaseModel | None = None` field. Subclasses
    may override this with a more specific BaseModel schema. The renderer
    always emits frontmatter at the very top of the document, before the
    title heading.
    """

    frontmatter: BaseModel | None = None
```

- [ ] **Step 4: Run test, confirm passes** — 7 passed.

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/template_model.py tests/agent_foundry/markdown/test_template_model.py
git commit -m "$(cat <<'EOF'
feat(markdown): add MarkdownDocument base class with optional frontmatter

Top-level base class. Inherits required title from MarkdownHeader;
adds frontmatter:BaseModel|None=None that subclasses override with their
specific schema. Default None means no frontmatter is rendered.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.2.4: Meta-validator scaffold + title rule

**Files:**
- Create: `src/agent_foundry/markdown/meta_validation.py`
- Create: `tests/agent_foundry/markdown/test_meta_validation.py`
- Modify: `src/agent_foundry/markdown/template_model.py` (wire `__pydantic_init_subclass__`)

**Dependencies:** Task 1.2.3.

- [ ] **Step 1: Write failing test**

Create `tests/agent_foundry/markdown/test_meta_validation.py`:

```python
"""Tests for class-definition-time meta-validation of template models."""

from __future__ import annotations

import pytest

from agent_foundry.markdown.errors import MarkdownTemplateError
from agent_foundry.markdown.template_model import MarkdownHeader


class TestTitleRule:
    """Every MarkdownHeader subclass must have title:str. Inherited by default;
    catches accidental override to a non-string type."""

    def test_subclass_inherits_title_passes(self):
        # No exception at class definition.
        class SimpleHeader(MarkdownHeader):
            pass

    def test_subclass_overrides_title_to_str_passes(self):
        from typing import Annotated
        from agent_foundry.markdown.annotations import TextTemplate

        class SimpleHeader(MarkdownHeader):
            title: Annotated[str, TextTemplate("X - {value}")]

    def test_subclass_overrides_title_to_non_str_raises(self):
        with pytest.raises(MarkdownTemplateError, match="title"):
            class BrokenHeader(MarkdownHeader):
                title: int  # type: ignore[assignment]

    def test_subclass_overrides_title_with_annotated_int_raises(self):
        """TextTemplate-annotated title is fine when underlying type is str;
        annotating a non-str type should still raise."""
        from typing import Annotated
        from agent_foundry.markdown.annotations import TextTemplate

        with pytest.raises(MarkdownTemplateError, match="title"):
            class BrokenHeader(MarkdownHeader):
                title: Annotated[int, TextTemplate("{value}")]  # type: ignore[arg-type]


class TestMetaValidationFiresWithFullFields:
    """The validator must see the subclass's body fields, not just inherited ones.
    This regression test pins the contract: __pydantic_init_subclass__ vs the
    earlier-firing __init_subclass__ make a real difference for our rules."""

    def test_subclass_body_fields_visible_in_validator(self):
        observed: dict = {}

        class Probe(MarkdownHeader):
            extra_field: str

            @classmethod
            def __pydantic_init_subclass__(cls, **kwargs):
                super().__pydantic_init_subclass__(**kwargs)
                observed["fields"] = list(cls.model_fields.keys())

        # The hook fires at class definition; body field must be visible.
        assert "extra_field" in observed["fields"]
        assert "title" in observed["fields"]
```

- [ ] **Step 2: Run test, confirm fails** — `ModuleNotFoundError: agent_foundry.markdown.meta_validation`.

- [ ] **Step 3: Implement meta-validation scaffold + title rule**

Create `src/agent_foundry/markdown/meta_validation.py`:

```python
"""Class-definition-time meta-validation for MarkdownHeader / MarkdownDocument
subclasses.

Triggered by the __pydantic_init_subclass__ hook on MarkdownHeader. Walks the
subclass's model_fields and enforces:
  1. Title rule          — title:str required (inherited; not overridden to non-str)
  2. Body order rule     — non-heading body fields must precede heading-introducing ones
  3. Frontmatter rule    — only on MarkdownDocument subclasses; first field; type BaseModel|None
  4. Type-compat rule    — every annotation has an allowed underlying type

Errors raise MarkdownTemplateError immediately so an offending class never
reaches runtime use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_foundry.markdown.errors import MarkdownTemplateError

if TYPE_CHECKING:
    from agent_foundry.markdown.template_model import MarkdownHeader


def validate_template_class(cls: type[MarkdownHeader]) -> None:
    """Run all meta-validation rules against a MarkdownHeader/MarkdownDocument subclass.
    Called from __pydantic_init_subclass__. Raises MarkdownTemplateError on any rule
    violation, including the offending field name and a fix suggestion in the message."""

    _check_title_rule(cls)
    # Subsequent rules added in following tasks:
    #   _check_body_order_rule(cls)
    #   _check_frontmatter_rule(cls)
    #   _check_type_compatibility_rule(cls)


def _check_title_rule(cls: type[MarkdownHeader]) -> None:
    """Title field must exist and be of type str."""
    fields = cls.model_fields
    if "title" not in fields:
        raise MarkdownTemplateError(
            f"{cls.__name__} is missing required 'title' field. "
            f"All MarkdownHeader subclasses inherit title:str; do not delete it."
        )
    title_field = fields["title"]
    if title_field.annotation is not str:
        raise MarkdownTemplateError(
            f"{cls.__name__}.title has type {title_field.annotation!r}, "
            f"expected str. The title field must remain a str (you may attach "
            f"annotations like TextTemplate via Annotated[str, TextTemplate(...)])."
        )
```

Modify `src/agent_foundry/markdown/template_model.py` to wire the hook on `MarkdownHeader`:

```python
"""Base classes for markdown-document templates."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MarkdownHeader(BaseModel):
    """Base class for any heading-shaped sub-document.
    [docstring as before]
    """

    title: str

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        # Defer the import to avoid circularity (meta_validation imports template_model
        # only via TYPE_CHECKING).
        from agent_foundry.markdown.meta_validation import validate_template_class

        validate_template_class(cls)


class MarkdownDocument(MarkdownHeader):
    """Top-level markdown document base class."""

    frontmatter: BaseModel | None = None
```

**Important — Pydantic hook choice (corrected after swarm review):** we use `__pydantic_init_subclass__`, NOT plain `__init_subclass__`. At plain `__init_subclass__` time, only inherited fields appear in `cls.model_fields` (subclass-declared fields haven't been built yet). The body-order rule (Task 1.2.5) and type-compat rule (Task 1.2.7) both iterate body fields — they would silently see only `title` and the bad-class tests would falsely pass. Pydantic's `__pydantic_init_subclass__` fires after Pydantic has fully populated `model_fields`, which is the contract our rules depend on.

- [ ] **Step 4: Run test, confirm passes** — 3 passed.

Also re-run the prior `test_template_model.py` to confirm nothing regressed:

Run: `pdm run pytest tests/agent_foundry/markdown/test_template_model.py -xvs`
Expected: 7 passed.

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/meta_validation.py src/agent_foundry/markdown/template_model.py tests/agent_foundry/markdown/test_meta_validation.py
git commit -m "$(cat <<'EOF'
feat(markdown): wire meta-validation hook with title rule

Adds the meta-validation scaffold and the first rule: title field must
exist and be of type str on every MarkdownHeader subclass. Hook fires
via __pydantic_init_subclass__ at class definition time, raising
MarkdownTemplateError on violation before any runtime use. The Pydantic
hook (rather than plain __init_subclass__) is required so model_fields
includes subclass body fields when the validator runs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.2.5: Body order rule

**Files:**
- Modify: `src/agent_foundry/markdown/meta_validation.py`
- Modify: `tests/agent_foundry/markdown/test_meta_validation.py`

**Dependencies:** Task 1.2.4.

- [ ] **Step 1: Append failing test**

```python
from typing import Annotated

from agent_foundry.markdown.annotations import (
    AsBulletList,
    AsCodeBlock,
    AsHeading,
    AsTable,
)


class TestBodyOrderRule:
    """Within a MarkdownHeader's body, non-heading fields must precede heading
    fields. Title is exempt (always the container heading); frontmatter is exempt
    (always rendered at top)."""

    def test_only_non_heading_body_fields_passes(self):
        class OkA(MarkdownHeader):
            code: Annotated[str, AsCodeBlock()]
            tags: Annotated[list[str], AsBulletList()]

    def test_only_heading_body_fields_passes(self):
        class OkB(MarkdownHeader):
            description: Annotated[str, AsHeading()]
            rationale: Annotated[str, AsHeading()]

    def test_non_heading_then_heading_passes(self):
        class OkC(MarkdownHeader):
            code: Annotated[str, AsCodeBlock()]
            description: Annotated[str, AsHeading()]

    def test_heading_then_non_heading_raises(self):
        with pytest.raises(MarkdownTemplateError, match="non-heading"):
            class Bad(MarkdownHeader):
                description: Annotated[str, AsHeading()]
                code: Annotated[str, AsCodeBlock()]

    def test_heading_then_table_raises(self):
        from pydantic import BaseModel

        class Row(BaseModel):
            a: str
            b: str

        with pytest.raises(MarkdownTemplateError, match="non-heading"):
            class Bad(MarkdownHeader):
                description: Annotated[str, AsHeading()]
                table: Annotated[list[Row], AsTable()]
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/agent_foundry/markdown/test_meta_validation.py::TestBodyOrderRule -xvs`
Expected: tests fail because `_check_body_order_rule` is not implemented.

- [ ] **Step 3: Implement body order rule**

Add to `src/agent_foundry/markdown/meta_validation.py`:

```python
from agent_foundry.markdown.annotations import (
    AsBulletList,
    AsCodeBlock,
    AsHeading,
    AsNumberedList,
    AsTable,
)

# Annotation types that DO NOT open a heading scope.
_NON_HEADING_ANNOTATIONS: tuple[type, ...] = (
    AsCodeBlock,
    AsTable,
    AsBulletList,
    AsNumberedList,
)


def _check_body_order_rule(cls: type[MarkdownHeader]) -> None:
    """Within the body (every field except 'title' and 'frontmatter'),
    non-heading fields must precede heading-introducing fields."""

    seen_heading = False
    seen_heading_name: str | None = None
    for name, field in cls.model_fields.items():
        if name in ("title", "frontmatter"):
            continue
        is_heading = _is_heading_introducing(field)
        if is_heading:
            seen_heading = True
            seen_heading_name = name
        elif seen_heading:
            raise MarkdownTemplateError(
                f"{cls.__name__}.{name} is non-heading "
                f"(annotation type {type(_get_role_annotation(field)).__name__}) "
                f"and follows {cls.__name__}.{seen_heading_name} "
                f"which is heading-introducing. Within a MarkdownHeader subclass's "
                f"body, all non-heading fields must precede all heading-introducing "
                f"fields. Reorder so '{name}' comes before '{seen_heading_name}', "
                f"or move '{name}' into '{seen_heading_name}''s body."
            )


def _is_heading_introducing(field: object) -> bool:
    """A body field is heading-introducing if it has AsHeading annotation,
    OR its type is a MarkdownHeader subclass, OR its type is list[MarkdownHeader-subclass]."""

    from agent_foundry.markdown.template_model import MarkdownHeader

    ann = _get_role_annotation(field)
    if isinstance(ann, AsHeading):
        return True
    field_type = field.annotation  # type: ignore[attr-defined]
    if isinstance(field_type, type) and issubclass(field_type, MarkdownHeader):
        return True
    # list[MarkdownHeader-subclass]
    from typing import get_args, get_origin

    if get_origin(field_type) in (list, list[object].__origin__ if hasattr(list[object], "__origin__") else list):  # noqa: E501
        args = get_args(field_type)
        if args and isinstance(args[0], type) and issubclass(args[0], MarkdownHeader):
            return True
    return False


def _get_role_annotation(field: object) -> object | None:
    """Extract the first markdown-role annotation from the field's metadata,
    or None if there isn't one."""

    metadata = getattr(field, "metadata", []) or []
    for m in metadata:
        if isinstance(m, _NON_HEADING_ANNOTATIONS) or isinstance(m, AsHeading):
            return m
    return None
```

Wire it into `validate_template_class`:

```python
def validate_template_class(cls: type[MarkdownHeader]) -> None:
    _check_title_rule(cls)
    _check_body_order_rule(cls)
    # Subsequent:
    #   _check_frontmatter_rule(cls)
    #   _check_type_compatibility_rule(cls)
```

- [ ] **Step 4: Run test, confirm passes** — all `TestBodyOrderRule` and `TestTitleRule` tests pass.

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/meta_validation.py tests/agent_foundry/markdown/test_meta_validation.py
git commit -m "$(cat <<'EOF'
feat(markdown): add body-order meta-validation rule

Within a MarkdownHeader subclass's body (everything except title and
frontmatter), non-heading fields must precede heading-introducing fields.
Heading-introducing = AsHeading on str, MarkdownHeader-typed field, or
list[MarkdownHeader-subclass]. Violation raises MarkdownTemplateError
naming both fields and suggesting a fix.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.2.6: Frontmatter rule

**Files:**
- Modify: `src/agent_foundry/markdown/meta_validation.py`
- Modify: `tests/agent_foundry/markdown/test_meta_validation.py`

**Dependencies:** Task 1.2.5.

- [ ] **Step 1: Append failing test**

```python
class TestFrontmatterRule:
    """Frontmatter is allowed only on MarkdownDocument subclasses, only as the
    first declared field, and only with type BaseModel | None."""

    def test_frontmatter_on_markdown_document_passes(self):
        from pydantic import BaseModel
        from agent_foundry.markdown.template_model import MarkdownDocument

        class FmSchema(BaseModel):
            x: int

        class Doc(MarkdownDocument):
            frontmatter: FmSchema | None = None

    def test_frontmatter_on_markdown_header_raises(self):
        from pydantic import BaseModel

        class FmSchema(BaseModel):
            x: int

        with pytest.raises(MarkdownTemplateError, match="frontmatter"):
            class BadHdr(MarkdownHeader):
                frontmatter: FmSchema | None = None  # not allowed: not a MarkdownDocument

    def test_frontmatter_not_first_field_raises(self):
        from pydantic import BaseModel
        from agent_foundry.markdown.template_model import MarkdownDocument

        class FmSchema(BaseModel):
            x: int

        with pytest.raises(MarkdownTemplateError, match="first"):
            class BadDoc(MarkdownDocument):
                summary: Annotated[str, AsHeading()]  # before frontmatter — bad
                frontmatter: FmSchema | None = None
```

- [ ] **Step 2: Run test, confirm fails**

- [ ] **Step 3: Implement frontmatter rule**

Add to `meta_validation.py`:

```python
def _check_frontmatter_rule(cls: type[MarkdownHeader]) -> None:
    """Frontmatter constraints:
       (a) declared (non-default) only on MarkdownDocument subclasses
       (b) when declared in the subclass body, must be the first field
       (c) type must be BaseModel | None
    Note: subclasses that inherit MarkdownDocument's default `frontmatter: BaseModel|None = None`
    without overriding it pass trivially.
    """

    from agent_foundry.markdown.template_model import MarkdownDocument

    # Detect whether the subclass declares 'frontmatter' itself (not just inherits).
    # We use __annotations__ which contains only the class's own annotations.
    own_annotations = getattr(cls, "__annotations__", {})
    if "frontmatter" not in own_annotations:
        return  # nothing declared in this subclass; rule passes

    # Rule (a): only MarkdownDocument subclasses may declare frontmatter.
    if not issubclass(cls, MarkdownDocument):
        raise MarkdownTemplateError(
            f"{cls.__name__} declares 'frontmatter' but inherits from MarkdownHeader, "
            f"not MarkdownDocument. Frontmatter is allowed only on MarkdownDocument "
            f"subclasses. Either change the base class to MarkdownDocument, or remove "
            f"the frontmatter field."
        )

    # Rule (b): must be the first field declared in this subclass.
    own_field_names = list(own_annotations.keys())
    if own_field_names[0] != "frontmatter":
        raise MarkdownTemplateError(
            f"{cls.__name__}: 'frontmatter' must be the first declared field "
            f"(currently field {own_field_names.index('frontmatter') + 1} of "
            f"{len(own_field_names)}). Move it to the top of the class body."
        )

    # Rule (c): type must be (BaseModel-subclass) | None.
    field_type = own_annotations["frontmatter"]
    if not _is_optional_basemodel(field_type):
        raise MarkdownTemplateError(
            f"{cls.__name__}.frontmatter has type {field_type!r}, expected a "
            f"BaseModel-subclass union with None (e.g. `MyFrontmatter | None`). "
        )


def _is_optional_basemodel(annotation: object) -> bool:
    """True iff the annotation is `BaseModel-subclass | None`."""
    from typing import get_args, get_origin
    from types import UnionType
    from typing import Union
    from pydantic import BaseModel

    origin = get_origin(annotation)
    if origin not in (Union, UnionType):
        return False
    args = get_args(annotation)
    if len(args) != 2:
        return False
    has_none = type(None) in args
    has_basemodel = any(
        isinstance(a, type) and issubclass(a, BaseModel) for a in args
    )
    return has_none and has_basemodel
```

Wire into `validate_template_class`.

- [ ] **Step 4: Run test, confirm passes**

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/meta_validation.py tests/agent_foundry/markdown/test_meta_validation.py
git commit -m "$(cat <<'EOF'
feat(markdown): add frontmatter meta-validation rule

Three sub-rules: (a) frontmatter declared only on MarkdownDocument
subclasses; (b) when declared, must be the first field of the subclass;
(c) type must be a BaseModel-subclass union with None. Subclasses that
just inherit the default pass trivially.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.2.7: Type-annotation compatibility rule

**Files:**
- Modify: `src/agent_foundry/markdown/meta_validation.py`
- Modify: `tests/agent_foundry/markdown/test_meta_validation.py`

**Dependencies:** Task 1.2.6.

- [ ] **Step 1: Append failing test**

```python
class TestTypeCompatibilityRule:
    """Each annotation has an allowed underlying type. Mismatches raise."""

    def test_as_heading_on_str_passes(self):
        class OkA(MarkdownHeader):
            description: Annotated[str, AsHeading()]

    def test_as_heading_on_int_raises(self):
        with pytest.raises(MarkdownTemplateError, match="AsHeading"):
            class BadA(MarkdownHeader):
                description: Annotated[int, AsHeading()]  # type: ignore[arg-type]

    def test_as_code_block_on_str_passes(self):
        class OkB(MarkdownHeader):
            code: Annotated[str, AsCodeBlock(language="python")]

    def test_as_code_block_on_int_raises(self):
        with pytest.raises(MarkdownTemplateError, match="AsCodeBlock"):
            class BadB(MarkdownHeader):
                code: Annotated[int, AsCodeBlock()]  # type: ignore[arg-type]

    def test_as_bullet_list_on_list_str_passes(self):
        class OkC(MarkdownHeader):
            tags: Annotated[list[str], AsBulletList()]

    def test_as_bullet_list_on_list_int_raises(self):
        with pytest.raises(MarkdownTemplateError, match="AsBulletList"):
            class BadC(MarkdownHeader):
                tags: Annotated[list[int], AsBulletList()]  # type: ignore[arg-type]

    def test_as_table_on_list_basemodel_passes(self):
        from pydantic import BaseModel

        class Row(BaseModel):
            a: str
            b: int

        class OkD(MarkdownHeader):
            rows: Annotated[list[Row], AsTable()]

    def test_as_table_on_list_str_raises(self):
        with pytest.raises(MarkdownTemplateError, match="AsTable"):
            class BadD(MarkdownHeader):
                rows: Annotated[list[str], AsTable()]  # type: ignore[arg-type]


class TestTextTemplateCompatibility:
    """TextTemplate has two valid contexts: MarkdownHeader.title (str) and
    list[MarkdownHeader-subclass] wrapper. All other uses raise."""

    def test_text_template_on_title_passes(self):
        from agent_foundry.markdown.annotations import TextTemplate

        class WithTemplate(MarkdownHeader):
            title: Annotated[str, TextTemplate("Section {value}")]

    def test_text_template_on_list_of_markdown_header_passes(self):
        from agent_foundry.markdown.annotations import TextTemplate

        class Item(MarkdownHeader):
            pass

        class HasItems(MarkdownHeader):
            items: Annotated[list[Item], TextTemplate("Custom Wrapper")]

    def test_text_template_on_str_body_field_raises(self):
        from agent_foundry.markdown.annotations import TextTemplate

        with pytest.raises(MarkdownTemplateError, match="TextTemplate"):
            class Bad(MarkdownHeader):
                description: Annotated[str, TextTemplate("Section {value}")]

    def test_text_template_on_list_str_raises(self):
        from agent_foundry.markdown.annotations import TextTemplate

        with pytest.raises(MarkdownTemplateError, match="TextTemplate"):
            class Bad(MarkdownHeader):
                tags: Annotated[list[str], TextTemplate("X")]
```

Add corresponding test to `TestBodyOrderRule` for list-of-MarkdownHeader heading-introducing case:

```python
class TestBodyOrderRuleListOfHeader:
    """list[MarkdownHeader-subclass] is heading-introducing; non-heading after it raises."""

    def test_non_heading_after_list_of_header_raises(self):
        class Item(MarkdownHeader):
            pass

        with pytest.raises(MarkdownTemplateError, match="non-heading"):
            class Bad(MarkdownHeader):
                items: list[Item]                      # heading-introducing
                code: Annotated[str, AsCodeBlock()]    # non-heading after

    def test_non_heading_after_single_header_raises(self):
        class Sub(MarkdownHeader):
            pass

        with pytest.raises(MarkdownTemplateError, match="non-heading"):
            class Bad(MarkdownHeader):
                child: Sub                              # heading-introducing
                code: Annotated[str, AsCodeBlock()]     # non-heading after
```

Add corresponding test to `TestFrontmatterRule` for non-optional frontmatter:

```python
    def test_frontmatter_non_optional_raises(self):
        from pydantic import BaseModel
        from agent_foundry.markdown.template_model import MarkdownDocument

        class FmSchema(BaseModel):
            x: int

        with pytest.raises(MarkdownTemplateError, match="frontmatter"):
            class BadDoc(MarkdownDocument):
                frontmatter: FmSchema  # missing | None — required type union
```

- [ ] **Step 2: Run test, confirm fails**

- [ ] **Step 3: Implement type-compatibility rule**

Add to `meta_validation.py`:

```python
from typing import get_args, get_origin

from pydantic import BaseModel as _BaseModel


def _check_type_compatibility_rule(cls: type[MarkdownHeader]) -> None:
    """Each annotation has an allowed underlying type:
       AsHeading       -> str
       AsCodeBlock     -> str
       AsTable         -> list[BaseModel-subclass]
       AsBulletList    -> list[str]
       AsNumberedList  -> list[str]
       TextTemplate    -> str (title field) OR a list[MarkdownHeader-subclass] (wrapper)
    Mismatches raise MarkdownTemplateError naming the field, the annotation,
    and the allowed type.
    """
    for name, field in cls.model_fields.items():
        if name in ("title", "frontmatter"):
            continue
        ann = _get_role_annotation(field)
        field_type = field.annotation
        _enforce_compat(cls, name, ann, field_type)


def _enforce_compat(cls: type, field_name: str, ann: object | None, field_type: object) -> None:
    from agent_foundry.markdown.annotations import TextTemplate
    from agent_foundry.markdown.template_model import MarkdownHeader

    if ann is None:
        return  # untyped body field; allowed (passthrough — see body-order rule)
    if isinstance(ann, AsHeading):
        if field_type is not str:
            _raise_compat(cls, field_name, "AsHeading", "str", field_type)
    elif isinstance(ann, AsCodeBlock):
        if field_type is not str:
            _raise_compat(cls, field_name, "AsCodeBlock", "str", field_type)
    elif isinstance(ann, AsBulletList):
        if not _is_list_of(field_type, str):
            _raise_compat(cls, field_name, "AsBulletList", "list[str]", field_type)
    elif isinstance(ann, AsNumberedList):
        if not _is_list_of(field_type, str):
            _raise_compat(cls, field_name, "AsNumberedList", "list[str]", field_type)
    elif isinstance(ann, AsTable):
        if not _is_list_of_basemodel(field_type):
            _raise_compat(cls, field_name, "AsTable", "list[BaseModel]", field_type)
    elif isinstance(ann, TextTemplate):
        # TextTemplate is allowed only on:
        #   - MarkdownHeader.title field (str) — handled by skip in caller
        #   - heading-introducing list-wrapper fields: list[MarkdownHeader-subclass]
        # Any other use is a definition-time error.
        if not _is_list_of_markdown_header(field_type):
            _raise_compat(
                cls, field_name, "TextTemplate",
                "MarkdownHeader.title (str) or list[MarkdownHeader-subclass]",
                field_type,
            )


def _is_list_of_markdown_header(field_type: object) -> bool:
    from agent_foundry.markdown.template_model import MarkdownHeader
    if get_origin(field_type) is not list:
        return False
    args = get_args(field_type)
    return (
        len(args) == 1
        and isinstance(args[0], type)
        and issubclass(args[0], MarkdownHeader)
    )


def _is_list_of(field_type: object, expected: type) -> bool:
    if get_origin(field_type) is not list:
        return False
    args = get_args(field_type)
    return len(args) == 1 and args[0] is expected


def _is_list_of_basemodel(field_type: object) -> bool:
    if get_origin(field_type) is not list:
        return False
    args = get_args(field_type)
    return (
        len(args) == 1
        and isinstance(args[0], type)
        and issubclass(args[0], _BaseModel)
    )


def _raise_compat(cls: type, field_name: str, ann_name: str, expected: str, actual: object) -> None:
    raise MarkdownTemplateError(
        f"{cls.__name__}.{field_name}: {ann_name} requires field type {expected}, "
        f"got {actual!r}. Either change the field's type, or use a different annotation."
    )
```

Wire into `validate_template_class`.

- [ ] **Step 4: Run test, confirm passes**

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/meta_validation.py tests/agent_foundry/markdown/test_meta_validation.py
git commit -m "$(cat <<'EOF'
feat(markdown): add annotation/field-type compatibility meta-rule

Each annotation has an allowed underlying type: AsHeading/AsCodeBlock
require str, AsBulletList/AsNumberedList require list[str], AsTable
requires list[BaseModel-subclass]. Mismatches raise at class-definition
time with a clear error.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 1.3 — Renderer (template + instance)

> **Note:** Tasks in this phase use a shared test fixture for compactness. Each task adds tests that depend on the fixtures in `tests/agent_foundry/markdown/fixtures/sample_models.py`, which is created in Task 1.3.1.

### Task 1.3.1: Test fixtures + renderer scaffold (skeleton output for `MarkdownHeader` with title only)

**Files:**
- Create: `tests/agent_foundry/markdown/fixtures/__init__.py`
- Create: `tests/agent_foundry/markdown/fixtures/sample_models.py`
- Create: `src/agent_foundry/markdown/renderer.py`
- Create: `tests/agent_foundry/markdown/test_renderer.py`

**Dependencies:** Task 1.2.7 (all meta-validation rules present, including `_get_role_annotation` defined in Task 1.2.5 which the renderer imports).

- [ ] **Step 1: Create fixtures**

Create `tests/agent_foundry/markdown/fixtures/__init__.py` (empty).

Create `tests/agent_foundry/markdown/fixtures/sample_models.py`:

```python
"""Reusable test models for the markdown machinery test suite."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel

from agent_foundry.markdown.annotations import (
    AsBulletList,
    AsCodeBlock,
    AsHeading,
    AsNumberedList,
    AsTable,
    TextTemplate,
)
from agent_foundry.markdown.template_model import MarkdownDocument, MarkdownHeader


class SimpleHeader(MarkdownHeader):
    """The smallest possible MarkdownHeader subclass — just a title."""


class HeaderWithSummary(MarkdownHeader):
    """A header with one labeled-section body field."""

    summary: Annotated[str, AsHeading()]


class FindingMetadata(BaseModel):
    sha: str
    severity: str


class Finding(MarkdownHeader):
    """A finding: title with ordinal-prefix template, then body sections."""

    title: Annotated[str, TextTemplate("Finding {ordinal} - {value}")]
    code: Annotated[str, AsCodeBlock(language="python")]
    tags: Annotated[list[str], AsBulletList()]
    description: Annotated[str, AsHeading()]
    rationale: Annotated[str, AsHeading()]


class ReviewerMetadata(BaseModel):
    change_set_name: str
    commit_range: str


class ReviewerOutput(MarkdownDocument):
    """The full Reviewer template — exercises every Phase-1 annotation."""

    frontmatter: ReviewerMetadata | None = None
    title: Annotated[str, TextTemplate("{value}")]
    next_steps: Annotated[list[str], AsNumberedList()]
    summary: Annotated[str, AsHeading()]
    findings: list[Finding]
```

- [ ] **Step 2: Write failing test**

Create `tests/agent_foundry/markdown/test_renderer.py`:

```python
"""Tests for the deterministic renderer."""

from __future__ import annotations

from agent_foundry.markdown.renderer import render_template
from tests.agent_foundry.markdown.fixtures.sample_models import SimpleHeader


class TestRenderTemplateSimpleHeader:
    """Skeleton output for the smallest possible header."""

    def test_simple_header_emits_h1_placeholder(self):
        out = render_template(SimpleHeader)
        # Top-level header at level 1; title placeholder uses field-description style.
        assert out.startswith("# ")
        assert out.endswith("\n")
```

- [ ] **Step 3: Run test, confirm fails** — `ModuleNotFoundError: agent_foundry.markdown.renderer`.

- [ ] **Step 4: Write minimal renderer scaffold**

Create `src/agent_foundry/markdown/renderer.py`:

```python
"""Deterministic markdown renderer for MarkdownHeader/MarkdownDocument templates and instances.

Two entry points:
  - render_template(model_class) -> str:  the annotated skeleton
  - render_instance(instance)    -> str:  a populated document

Both walk fields in declaration order, dispatch on field role (structural vs
annotation-driven), and emit the corresponding markdown. Heading levels are
inferred from rendering context (top-level model is level 1; nested headers
recurse with level + 1). A render-time guard raises if any heading would
emit at level > 6.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_foundry.markdown.errors import MarkdownTemplateError

if TYPE_CHECKING:
    from agent_foundry.markdown.template_model import MarkdownHeader


_MAX_HEADING_LEVEL = 6


def render_template(model_class: type[MarkdownHeader], *, current_level: int = 1) -> str:
    """Render the annotated skeleton template for a MarkdownHeader subclass.

    The skeleton has every heading filled in with its derived text and every body
    region filled with placeholder text (`<!-- field description -->` comments
    derived from `Field(description=...)` where present, or generic placeholders
    otherwise).
    """
    _guard_heading_level(model_class, current_level)
    title_text = _derive_title_text_for_template(model_class)
    parts: list[str] = [f"{'#' * current_level} {title_text}", ""]
    return "\n".join(parts).rstrip() + "\n"


def _derive_title_text_for_template(model_class: type[MarkdownHeader]) -> str:
    """Skeleton title text — just a placeholder using the class name."""
    return f"<!-- {model_class.__name__} title -->"


def _guard_heading_level(model_class: type, level: int) -> None:
    if level > _MAX_HEADING_LEVEL:
        raise MarkdownTemplateError(
            f"Cannot render {model_class.__name__} at heading level {level}; "
            f"markdown supports a maximum of level {_MAX_HEADING_LEVEL}. "
            f"Reduce nesting in the template."
        )
```

- [ ] **Step 5: Run test, confirm passes**

- [ ] **Step 6: Lint, format, typecheck**

- [ ] **Step 7: Commit**

```bash
git add src/agent_foundry/markdown/renderer.py tests/agent_foundry/markdown/test_renderer.py tests/agent_foundry/markdown/fixtures/__init__.py tests/agent_foundry/markdown/fixtures/sample_models.py
git commit -m "$(cat <<'EOF'
feat(markdown): renderer scaffold + render_template for SimpleHeader

Initial deterministic renderer with render_template entry point. Handles
the simplest case (a MarkdownHeader subclass with no body fields). Adds
the depth-6 heading-level guard. Reusable test fixtures introduced in
fixtures/sample_models.py.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.3.2: Render `AsHeading`-on-str body fields

**Files:**
- Modify: `src/agent_foundry/markdown/renderer.py`
- Modify: `tests/agent_foundry/markdown/test_renderer.py`

**Dependencies:** Task 1.3.1.

- [ ] **Step 1: Append failing test**

```python
from tests.agent_foundry.markdown.fixtures.sample_models import HeaderWithSummary


class TestRenderHeadingBodyFields:
    """AsHeading on str body field renders as `## FieldName` + placeholder body."""

    def test_summary_field_renders_at_level_2(self):
        out = render_template(HeaderWithSummary)
        # Title at level 1, summary at level 2.
        assert "# " in out
        assert "## Summary" in out

    def test_summary_field_field_name_is_title_cased(self):
        # snake_case → Title Case
        out = render_template(HeaderWithSummary)
        assert "## Summary" in out
        assert "## summary" not in out
```

- [ ] **Step 2: Run test, confirm fails**

- [ ] **Step 3: Extend the renderer**

Modify `render_template` to walk body fields:

```python
from agent_foundry.markdown.annotations import AsHeading


def render_template(model_class: type[MarkdownHeader], *, current_level: int = 1) -> str:
    _guard_heading_level(model_class, current_level)
    title_text = _derive_title_text_for_template(model_class)
    parts: list[str] = [f"{'#' * current_level} {title_text}", ""]

    body_level = current_level + 1
    for name, field in model_class.model_fields.items():
        if name in ("title", "frontmatter"):
            continue
        rendered = _render_body_field_template(name, field, body_level, model_class)
        if rendered:
            parts.append(rendered)
            parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def _render_body_field_template(
    name: str,
    field: object,
    level: int,
    owning_class: type,
) -> str:
    """Render the skeleton output for one body field."""
    from agent_foundry.markdown.meta_validation import _get_role_annotation

    ann = _get_role_annotation(field)
    if isinstance(ann, AsHeading):
        _guard_heading_level(owning_class, level)
        heading_text = _snake_to_title(name)
        description_comment = _description_comment(field)
        return f"{'#' * level} {heading_text}\n\n{description_comment}"
    return ""  # other shapes added in subsequent tasks


def _snake_to_title(name: str) -> str:
    """Convert snake_case to Title Case (e.g. 'change_set_name' → 'Change Set Name')."""
    return " ".join(word.capitalize() for word in name.split("_"))


def _description_comment(field: object) -> str:
    desc = getattr(field, "description", None)
    if desc:
        return f"<!-- {desc} -->"
    return "<!-- field body -->"
```

Note: `_get_role_annotation` is a private helper from `meta_validation.py`. To avoid coupling, consider moving it to a shared internal module (e.g., `_introspection.py`) once the renderer needs it. For Task 1.3.2 we import from meta_validation (it's all internal `_`-prefixed); revisit during self-review.

- [ ] **Step 4: Run test, confirm passes**

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/renderer.py tests/agent_foundry/markdown/test_renderer.py
git commit -m "$(cat <<'EOF'
feat(markdown): render AsHeading-on-str body fields in templates

Body field walking with field-name → Title Case heading derivation.
Renders at parent's body level (current + 1). Uses Field(description=...)
in body comment when set; otherwise a generic placeholder.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.3.3: Render `AsCodeBlock`, `AsBulletList`, `AsNumberedList` body fields

**Files:**
- Modify: `src/agent_foundry/markdown/renderer.py`
- Modify: `tests/agent_foundry/markdown/test_renderer.py`

**Dependencies:** Task 1.3.2.

- [ ] **Step 1: Append failing test**

```python
from typing import Annotated

from agent_foundry.markdown.annotations import AsBulletList, AsCodeBlock, AsNumberedList
from agent_foundry.markdown.template_model import MarkdownHeader


class TestRenderNonHeadingBodyFields:
    """Code blocks, bullet lists, numbered lists render as their markdown forms."""

    def test_code_block_template_emits_fenced_block(self):
        class WithCode(MarkdownHeader):
            snippet: Annotated[str, AsCodeBlock(language="python")]

        out = render_template(WithCode)
        assert "```python" in out
        assert "```" in out

    def test_bullet_list_template_emits_dash_placeholder(self):
        class WithBullets(MarkdownHeader):
            tags: Annotated[list[str], AsBulletList()]

        out = render_template(WithBullets)
        assert "- " in out

    def test_numbered_list_template_emits_one_dot_placeholder(self):
        class WithNumbers(MarkdownHeader):
            steps: Annotated[list[str], AsNumberedList()]

        out = render_template(WithNumbers)
        assert "1. " in out
```

- [ ] **Step 2: Run test, confirm fails**

- [ ] **Step 3: Extend the renderer**

Add handlers in `_render_body_field_template`:

```python
from agent_foundry.markdown.annotations import (
    AsBulletList,
    AsCodeBlock,
    AsHeading,
    AsNumberedList,
)


def _render_body_field_template(
    name: str,
    field: object,
    level: int,
    owning_class: type,
) -> str:
    from agent_foundry.markdown.meta_validation import _get_role_annotation

    ann = _get_role_annotation(field)
    if isinstance(ann, AsHeading):
        _guard_heading_level(owning_class, level)
        heading_text = _snake_to_title(name)
        description_comment = _description_comment(field)
        return f"{'#' * level} {heading_text}\n\n{description_comment}"
    if isinstance(ann, AsCodeBlock):
        lang = ann.language or ""
        return f"```{lang}\n<!-- {name} code -->\n```"
    if isinstance(ann, AsBulletList):
        return f"- <!-- {name} item 1 -->\n- <!-- {name} item 2 -->"
    if isinstance(ann, AsNumberedList):
        return f"1. <!-- {name} item 1 -->\n2. <!-- {name} item 2 -->"
    return ""  # AsTable + heading-introducing types in subsequent tasks
```

- [ ] **Step 4: Run test, confirm passes**

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/renderer.py tests/agent_foundry/markdown/test_renderer.py
git commit -m "$(cat <<'EOF'
feat(markdown): render code-block, bullet-list, numbered-list body fields

Skeleton output uses the appropriate markdown form for each annotation;
placeholder comments label what each region is for.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.3.4: Render `AsTable` body fields

**Files:**
- Modify: `src/agent_foundry/markdown/renderer.py`
- Modify: `tests/agent_foundry/markdown/test_renderer.py`

**Dependencies:** Task 1.3.3.

- [ ] **Step 1: Append failing test**

```python
from pydantic import BaseModel

from agent_foundry.markdown.annotations import AsTable


class TestRenderTable:
    """AsTable on list[BaseModel-with-scalars] renders as a markdown table
    whose columns are the inner model's field names."""

    def test_table_template_emits_pipe_header_and_separator(self):
        class Row(BaseModel):
            path: str
            lines: int

        class WithTable(MarkdownHeader):
            files: Annotated[list[Row], AsTable()]

        out = render_template(WithTable)
        assert "| Path | Lines |" in out
        assert "|---|---|" in out
```

- [ ] **Step 2: Run test, confirm fails**

- [ ] **Step 3: Extend the renderer**

Add to `_render_body_field_template`:

```python
from typing import get_args, get_origin

from agent_foundry.markdown.annotations import AsTable
from pydantic import BaseModel


def _render_table_template(name: str, field: object) -> str:
    field_type = field.annotation  # type: ignore[attr-defined]
    if get_origin(field_type) is not list:
        return ""  # validated by meta-rule; defensive
    inner = get_args(field_type)[0]
    if not (isinstance(inner, type) and issubclass(inner, BaseModel)):
        return ""
    column_names = [_snake_to_title(fname) for fname in inner.model_fields]
    header = "| " + " | ".join(column_names) + " |"
    sep = "|" + "|".join(["---"] * len(column_names)) + "|"
    placeholder = "| " + " | ".join([f"<!-- {fn} -->" for fn in inner.model_fields]) + " |"
    return f"{header}\n{sep}\n{placeholder}"


# Add to the dispatcher:
#     if isinstance(ann, AsTable):
#         return _render_table_template(name, field)
```

- [ ] **Step 4: Run test, confirm passes**

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/renderer.py tests/agent_foundry/markdown/test_renderer.py
git commit -m "$(cat <<'EOF'
feat(markdown): render AsTable body fields as markdown tables

Columns derived from the inner model's field names (Title Cased).
Skeleton row uses placeholder comments per cell.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.3.5: Render heading-introducing fields — single nested `MarkdownHeader` and `list[MarkdownHeader-subclass]` (with ordinal counter)

**Files:**
- Modify: `src/agent_foundry/markdown/renderer.py`
- Modify: `tests/agent_foundry/markdown/test_renderer.py`

**Dependencies:** Task 1.3.4.

- [ ] **Step 1: Append failing test**

```python
from tests.agent_foundry.markdown.fixtures.sample_models import Finding


class TestRenderHeadingIntroducingFields:
    """Single MarkdownHeader-typed field renders as a sub-heading (with title
    from instance, not field name). list[MarkdownHeader-subclass] renders as
    a wrapper heading (text from field name) + each item at wrapper-level + 1
    with ordinal counter."""

    def test_list_of_finding_template_emits_wrapper_heading(self):
        class WithFindings(MarkdownHeader):
            findings: list[Finding]

        out = render_template(WithFindings)
        assert "## Findings" in out  # wrapper heading

    def test_finding_item_template_emits_ordinal_placeholder(self):
        class WithFindings(MarkdownHeader):
            findings: list[Finding]

        out = render_template(WithFindings)
        # The Finding subdocument's title carries TextTemplate("Finding {ordinal} - {value}")
        # In skeleton form, ordinal is shown as "{ordinal}" or a literal placeholder.
        assert "Finding {ordinal}" in out or "### Finding 1" in out
```

- [ ] **Step 2: Run test, confirm fails**

- [ ] **Step 3: Extend the renderer**

Add a recursion path for nested headers and lists in `_render_body_field_template`:

```python
def _render_body_field_template(
    name: str,
    field: object,
    level: int,
    owning_class: type,
) -> str:
    from agent_foundry.markdown.template_model import MarkdownHeader

    ann = _get_role_annotation(field)
    field_type = field.annotation

    # Existing handlers...

    # Single MarkdownHeader-typed field
    if isinstance(field_type, type) and issubclass(field_type, MarkdownHeader):
        # Recurse: render the nested header at this level.
        return render_template(field_type, current_level=level)

    # list[MarkdownHeader-subclass]
    if get_origin(field_type) is list:
        args = get_args(field_type)
        if args and isinstance(args[0], type) and issubclass(args[0], MarkdownHeader):
            # Wrapper text: TextTemplate annotation (literal-only) overrides default field-name-derived text
            wrapper_text = _resolve_wrapper_text_render(name, field)
            _guard_heading_level(owning_class, level)
            wrapper = f"{'#' * level} {wrapper_text}"
            item_template = render_template(args[0], current_level=level + 1)
            return f"{wrapper}\n\n{item_template}"


def _resolve_wrapper_text_render(field_name: str, field: object) -> str:
    """Mirror of the projector's wrapper-text resolution. TextTemplate
    overrides field-name-derived default."""
    from agent_foundry.markdown.annotations import TextTemplate
    metadata = getattr(field, "metadata", []) or []
    for m in metadata:
        if isinstance(m, TextTemplate):
            return m.template
    return _snake_to_title(field_name)

    # Existing AsHeading / AsCodeBlock / etc. handlers...
    return ""
```

For TextTemplate substitution in items (e.g., `"Finding {ordinal} - {value}"`), the skeleton renders the literal template since there's no real `{ordinal}` value or `{value}` to fill in:

```python
# In render_template for a MarkdownHeader subclass: when title field has a TextTemplate
# annotation, use the template literal as the skeleton title text rather than the
# class-name placeholder.
def _derive_title_text_for_template(model_class: type[MarkdownHeader]) -> str:
    title_field = model_class.model_fields.get("title")
    if title_field:
        from agent_foundry.markdown.annotations import TextTemplate
        for m in (title_field.metadata or []):
            if isinstance(m, TextTemplate):
                return m.template  # show the literal template in the skeleton
    return f"<!-- {model_class.__name__} title -->"
```

- [ ] **Step 4: Run test, confirm passes**

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/renderer.py tests/agent_foundry/markdown/test_renderer.py
git commit -m "$(cat <<'EOF'
feat(markdown): render nested MarkdownHeader and list[MarkdownHeader] fields

Single MarkdownHeader-typed field recurses at the parent's body level.
list[MarkdownHeader-subclass] emits a wrapper heading (text from field
name) plus the item subdocument at wrapper + 1. TextTemplate on a title
field is shown literally in the skeleton.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.3.6: `render_instance` for populated documents

**Files:**
- Modify: `src/agent_foundry/markdown/renderer.py`
- Modify: `tests/agent_foundry/markdown/test_renderer.py`

**Dependencies:** Task 1.3.5.

- [ ] **Step 1: Write failing test**

```python
from tests.agent_foundry.markdown.fixtures.sample_models import (
    Finding,
    HeaderWithSummary,
    ReviewerOutput,
    ReviewerMetadata,
)


class TestRenderInstance:
    """render_instance produces a populated document from a model instance."""

    def test_simple_header_with_summary(self):
        from agent_foundry.markdown.renderer import render_instance

        h = HeaderWithSummary(title="My Doc", summary="The work is good.")
        out = render_instance(h)
        assert out.startswith("# My Doc")
        assert "## Summary" in out
        assert "The work is good." in out

    def test_finding_uses_text_template(self):
        from agent_foundry.markdown.renderer import render_instance

        f = Finding(
            title="missing tests",
            code="def foo(): pass",
            tags=["test", "coverage"],
            description="No unit tests exist.",
            rationale="Project requires TDD.",
        )
        out = render_instance(f, current_level=3)
        assert "### Finding 1 - missing tests" in out
        assert "```python" in out
        assert "def foo(): pass" in out
        assert "- test" in out
        assert "- coverage" in out

    def test_full_reviewer_output_with_frontmatter(self):
        from agent_foundry.markdown.renderer import render_instance

        review = ReviewerOutput(
            title="Review of cs7-plan4",
            frontmatter=ReviewerMetadata(change_set_name="cs7", commit_range="abc..def"),
            next_steps=["A", "B"],
            summary="Looks good.",
            findings=[
                Finding(
                    title="t1",
                    code="x",
                    tags=[],
                    description="d",
                    rationale="r",
                )
            ],
        )
        out = render_instance(review)
        assert out.startswith("---\n")
        assert "change_set_name: cs7" in out
        assert "# Review of cs7-plan4" in out
        assert "1. A" in out
        assert "## Summary" in out
        assert "## Findings" in out
        assert "### Finding 1 - t1" in out
```

- [ ] **Step 2: Run test, confirm fails**

- [ ] **Step 3: Implement `render_instance`**

```python
def render_instance(
    instance: MarkdownHeader,
    *,
    current_level: int = 1,
    ordinal: int | None = None,
) -> str:
    """Render a populated MarkdownHeader (or MarkdownDocument) instance to markdown text.

    `ordinal` is the 1-based position of this instance when rendered as a list item
    of a parent list field. For standalone calls, ordinal=None and TextTemplate's
    {ordinal} placeholder defaults to '1' (see _resolve_title_text).
    """

    from agent_foundry.markdown.template_model import MarkdownDocument

    parts: list[str] = []

    # 1. Frontmatter at the very top, only on MarkdownDocument with frontmatter set
    if isinstance(instance, MarkdownDocument) and instance.frontmatter is not None:
        parts.append(_render_frontmatter_instance(instance.frontmatter))

    # 2. Title at current_level
    _guard_heading_level(type(instance), current_level)
    title_text = _resolve_title_text(instance, ordinal=ordinal)
    parts.append(f"{'#' * current_level} {title_text}")

    # 3. Body fields in declaration order at current_level + 1
    body_level = current_level + 1
    for name, field in type(instance).model_fields.items():
        if name in ("title", "frontmatter"):
            continue
        value = getattr(instance, name)
        rendered = _render_body_field_instance(name, field, value, body_level, type(instance))
        if rendered:
            parts.append(rendered)

    return "\n\n".join(p for p in parts if p).rstrip() + "\n"


def _resolve_title_text(instance: MarkdownHeader, *, ordinal: int | None) -> str:
    """Apply TextTemplate substitution if present; otherwise return the raw value.

    Standalone rendering (ordinal=None) of an instance whose title template
    references {ordinal} substitutes the literal `1` — this lets the agent
    or user render a single instance for inspection/templating without the
    placeholder appearing in the output. List-context rendering passes the
    real 1-based ordinal.
    """
    from agent_foundry.markdown.annotations import TextTemplate

    title_field = type(instance).model_fields.get("title")
    if title_field:
        for m in (title_field.metadata or []):
            if isinstance(m, TextTemplate):
                template = m.template
                # Substitute {ordinal} — default to 1 when standalone (no list parent)
                if "{ordinal}" in template:
                    template = template.replace("{ordinal}", str(ordinal if ordinal is not None else 1))
                if "{value}" in template:
                    template = template.replace("{value}", instance.title)
                return template
    return instance.title


def _render_frontmatter_instance(frontmatter: BaseModel) -> str:
    import yaml

    data = frontmatter.model_dump()
    yaml_text = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    return f"---\n{yaml_text}---"


def _render_body_field_instance(
    name: str,
    field: object,
    value: object,
    level: int,
    owning_class: type,
) -> str:
    """Render one body field's actual value to markdown."""
    from agent_foundry.markdown.template_model import MarkdownHeader

    ann = _get_role_annotation(field)
    field_type = field.annotation

    if isinstance(ann, AsHeading):
        _guard_heading_level(owning_class, level)
        heading_text = _snake_to_title(name)
        body_text = str(value) if value is not None else ""
        return f"{'#' * level} {heading_text}\n\n{body_text}"
    if isinstance(ann, AsCodeBlock):
        lang = ann.language or ""
        return f"```{lang}\n{value}\n```"
    if isinstance(ann, AsBulletList):
        items = "\n".join(f"- {item}" for item in (value or []))
        return items
    if isinstance(ann, AsNumberedList):
        items = "\n".join(f"{i + 1}. {item}" for i, item in enumerate(value or []))
        return items
    if isinstance(ann, AsTable):
        return _render_table_instance(field_type, value)
    if isinstance(field_type, type) and issubclass(field_type, MarkdownHeader):
        return render_instance(value, current_level=level)
    if get_origin(field_type) is list:
        args = get_args(field_type)
        if args and isinstance(args[0], type) and issubclass(args[0], MarkdownHeader):
            wrapper_text = _resolve_wrapper_text_render(name, field)
            _guard_heading_level(owning_class, level)
            wrapper = f"{'#' * level} {wrapper_text}"
            if not value:
                # Empty list: emit only the wrapper heading. Round-trips correctly.
                return wrapper
            item_parts = []
            for ordinal, item in enumerate(value, start=1):
                # Render the item with the correct ordinal threaded through.
                rendered = render_instance(item, current_level=level + 1, ordinal=ordinal)
                item_parts.append(rendered)
            return wrapper + "\n\n" + "\n\n".join(item_parts)
    return ""


def _render_table_instance(field_type: object, value: object) -> str:
    inner = get_args(field_type)[0]
    column_names = [_snake_to_title(fname) for fname in inner.model_fields]
    header = "| " + " | ".join(column_names) + " |"
    sep = "|" + "|".join(["---"] * len(column_names)) + "|"
    rows = []
    for item in (value or []):
        cells = [str(getattr(item, fname)) for fname in inner.model_fields]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, sep, *rows])


def _replace_first_heading_text(rendered: str, new_title: str, *, level: int) -> str:
    """Replace the first heading line at the given level with one containing new_title."""
    lines = rendered.split("\n")
    prefix = "#" * level + " "
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = prefix + new_title
            break
    return "\n".join(lines)
```

Note: the `_render_body_field_instance` recursion for `list[MarkdownHeader-subclass]` does an awkward "render then patch the title for ordinal substitution" dance. Cleaner: thread an `ordinal` parameter through `render_instance`. The implementer should refactor during this task.

- [ ] **Step 4: Run test, confirm passes**

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/renderer.py tests/agent_foundry/markdown/test_renderer.py
git commit -m "$(cat <<'EOF'
feat(markdown): render_instance for populated MarkdownHeader instances

Renders a populated instance to markdown: frontmatter at top (if
MarkdownDocument with frontmatter set), title with TextTemplate
substitution, body fields in declaration order. Handles all six
annotation types and the heading-introducing nested/list shapes.
TextTemplate ordinal substitution wired in for list-item titles.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.3.7: Render-time depth-6 guard tests

**Files:**
- Modify: `tests/agent_foundry/markdown/test_renderer.py`

**Dependencies:** Task 1.3.6.

- [ ] **Step 1: Write failing test**

```python
class TestDepthGuard:
    """The depth-6 guard fires when nested rendering would emit a level-7 heading."""

    def test_seven_levels_deep_raises(self):
        # Build a 7-level-deep nested chain.
        class L7(MarkdownHeader):
            inner: Annotated[str, AsHeading()]

        class L6(MarkdownHeader):
            inner: L7

        class L5(MarkdownHeader):
            inner: L6

        class L4(MarkdownHeader):
            inner: L5

        class L3(MarkdownHeader):
            inner: L4

        class L2(MarkdownHeader):
            inner: L3

        class L1(MarkdownHeader):
            inner: L2

        # Rendering at top-level (level 1) means inner field renders at level 2;
        # its child at 3; and so on. L7's title would be at level 7.
        with pytest.raises(MarkdownTemplateError, match="level 7"):
            render_template(L1)
```

- [ ] **Step 2: Run test, confirm fails or passes** depending on whether the guard fires correctly. If it doesn't, adjust the renderer.

- [ ] **Step 3: Implementation should already work** (the guard was added in Task 1.3.1). If the test fails because the guard didn't fire at the right point, debug and fix.

- [ ] **Step 4: Run test, confirm passes**

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit (if any code changed)**

```bash
git add tests/agent_foundry/markdown/test_renderer.py [src/agent_foundry/markdown/renderer.py]
git commit -m "$(cat <<'EOF'
test(markdown): cover depth-6 heading guard with 7-level model

Confirms that render_template raises MarkdownTemplateError when nested
rendering would emit a level-7 heading. The guard is render-time
because depth depends on usage context.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 1.4 — Parser/validator

The parser pipeline has three stages: AST → element tree (Task 1.4.1), element tree → projector that constructs the typed instance (Task 1.4.2 + 1.4.3), and the public `validate_markdown` glue (Task 1.4.4). Each is its own module to keep responsibilities small.

### Task 1.4.1: AST normalizer (markdown-it-py AST → element tree)

**Files:**
- Create: `src/agent_foundry/markdown/_ast_normalizer.py`
- Create: `tests/agent_foundry/markdown/test_ast_normalizer.py`

**Dependencies:** Tasks 1.1.7 (MarkdownParagraph element), 1.2.1 (markdown-it-py dep), 1.2.7 (`_get_role_annotation` available — projector layer borrows it), 1.3.1 (fixture file `sample_models.py` for downstream tests in 1.4.2+).

- [ ] **Step 1: Write failing test**

Create `tests/agent_foundry/markdown/test_ast_normalizer.py`:

```python
"""Tests for the markdown-it-py AST → BlockElement tree normalizer."""

from __future__ import annotations

from agent_foundry.markdown._ast_normalizer import (
    normalize,
    NormalizedDocument,
)
from agent_foundry.markdown.elements import (
    MarkdownBulletList,
    MarkdownCodeBlock,
    MarkdownHeading,
    MarkdownNumberedList,
    MarkdownTable,
)


class TestNormalizeHeadings:
    def test_single_h1_with_no_body(self):
        doc = normalize("# Hello\n")
        assert isinstance(doc, NormalizedDocument)
        assert doc.frontmatter is None
        assert len(doc.blocks) == 1
        h = doc.blocks[0]
        assert isinstance(h, MarkdownHeading)
        assert h.text == "Hello"
        assert h.body == []

    def test_h1_with_h2_inside_scope(self):
        doc = normalize("# Top\n\n## Inner\n")
        h1 = doc.blocks[0]
        assert isinstance(h1, MarkdownHeading)
        assert h1.text == "Top"
        assert len(h1.body) == 1
        assert isinstance(h1.body[0], MarkdownHeading)
        assert h1.body[0].text == "Inner"

    def test_two_sibling_h1_headings(self):
        doc = normalize("# A\n\n# B\n")
        assert len(doc.blocks) == 2
        assert all(isinstance(b, MarkdownHeading) for b in doc.blocks)
        assert doc.blocks[0].text == "A"
        assert doc.blocks[1].text == "B"


class TestNormalizeCodeBlock:
    def test_fenced_code_with_language(self):
        doc = normalize("# Top\n\n```python\nx = 1\n```\n")
        h = doc.blocks[0]
        assert len(h.body) == 1
        c = h.body[0]
        assert isinstance(c, MarkdownCodeBlock)
        assert c.language == "python"
        assert c.content == "x = 1\n"


class TestNormalizeLists:
    def test_bullet_list(self):
        doc = normalize("# Top\n\n- a\n- b\n")
        h = doc.blocks[0]
        assert len(h.body) == 1
        bl = h.body[0]
        assert isinstance(bl, MarkdownBulletList)
        assert bl.items == ["a", "b"]

    def test_numbered_list(self):
        doc = normalize("# Top\n\n1. a\n2. b\n")
        h = doc.blocks[0]
        nl = h.body[0]
        assert isinstance(nl, MarkdownNumberedList)
        assert nl.items == ["a", "b"]


class TestNormalizeTable:
    def test_gfm_table(self):
        md = (
            "# Top\n\n"
            "| Path | Lines |\n"
            "|------|-------|\n"
            "| a.py | 12    |\n"
            "| b.py | 7     |\n"
        )
        doc = normalize(md)
        h = doc.blocks[0]
        t = h.body[0]
        assert isinstance(t, MarkdownTable)
        assert t.columns == ["Path", "Lines"]
        assert len(t.rows) == 2
        assert t.rows[0].cells == ["a.py", "12"]


class TestNormalizeFrontmatter:
    def test_yaml_frontmatter(self):
        md = "---\nname: x\nversion: 1\n---\n\n# Top\n"
        doc = normalize(md)
        assert doc.frontmatter is not None
        assert doc.frontmatter.parsed == {"name": "x", "version": 1}
        assert "name: x" in doc.frontmatter.raw_yaml


class TestNormalizeParagraph:
    """Paragraphs INSIDE a heading body must be captured as MarkdownParagraph
    elements. Without this, AsHeading body content is silently dropped."""

    def test_heading_with_paragraph_body(self):
        from agent_foundry.markdown.elements import MarkdownParagraph

        doc = normalize("# Top\n\nThe body content here.\n")
        h = doc.blocks[0]
        assert isinstance(h, MarkdownHeading)
        assert len(h.body) == 1
        p = h.body[0]
        assert isinstance(p, MarkdownParagraph)
        assert p.content == "The body content here."

    def test_heading_with_two_paragraphs(self):
        from agent_foundry.markdown.elements import MarkdownParagraph

        doc = normalize("# Top\n\nFirst paragraph.\n\nSecond paragraph.\n")
        h = doc.blocks[0]
        assert len(h.body) == 2
        assert isinstance(h.body[0], MarkdownParagraph)
        assert isinstance(h.body[1], MarkdownParagraph)
        assert h.body[0].content == "First paragraph."
        assert h.body[1].content == "Second paragraph."
```

- [ ] **Step 2: Run test, confirm fails** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the normalizer**

Create `src/agent_foundry/markdown/_ast_normalizer.py`:

```python
"""Normalize markdown-it-py AST tokens into a tree of typed BlockElement
instances + an optional MarkdownFrontmatter at the top.

Why a separate module: keeps the AST-token → typed-tree concern decoupled from
the projector (element-tree → domain instance). Tests can drive each layer
independently.
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml
from markdown_it import MarkdownIt
from markdown_it.token import Token

from agent_foundry.markdown.elements import (
    BlockElement,
    MarkdownBulletList,
    MarkdownCodeBlock,
    MarkdownFrontmatter,
    MarkdownHeading,
    MarkdownNumberedList,
    MarkdownParagraph,
    MarkdownTable,
    MarkdownTableRow,
)


@dataclass
class NormalizedDocument:
    """The output of `normalize()` — frontmatter (or None) plus the top-level
    block sequence. Each top-level heading carries its scoped body recursively."""

    frontmatter: MarkdownFrontmatter | None
    blocks: list[BlockElement]


def normalize(markdown: str) -> NormalizedDocument:
    """Parse markdown text and produce a normalized element tree."""

    fm, body = _split_frontmatter(markdown)
    # Use commonmark + the table plugin. NOT MarkdownIt("gfm-like"): that
    # preset enables the linkify rule, which requires the linkify-it-py
    # package (not in our deps) and crashes at parse time without it.
    md = MarkdownIt("commonmark").enable("table")
    tokens = md.parse(body)
    flat = _tokens_to_blocks(tokens)
    blocks_with_scope = _nest_headings_by_level(flat)
    return NormalizedDocument(frontmatter=fm, blocks=blocks_with_scope)


def _split_frontmatter(markdown: str) -> tuple[MarkdownFrontmatter | None, str]:
    if not markdown.startswith("---\n"):
        return None, markdown
    end = markdown.find("\n---\n", 4)
    if end == -1:
        return None, markdown
    raw_yaml = markdown[4:end + 1]  # include trailing newline of body
    rest = markdown[end + len("\n---\n") :]
    parsed = yaml.safe_load(raw_yaml) or {}
    return MarkdownFrontmatter(raw_yaml=raw_yaml, parsed=parsed), rest


@dataclass
class _FlatBlock:
    """Pass-1 wrapper that carries the AST heading level alongside the typed
    element. Used only inside the normalizer; never escapes the module."""

    element: BlockElement
    level: int | None  # set only for MarkdownHeading


def _tokens_to_blocks(tokens: list[Token]) -> list[_FlatBlock]:
    """First pass: convert flat token stream into a flat list of `_FlatBlock`
    wrappers. Headings carry their AST level via the wrapper (pass 2 uses it
    to nest scopes); other elements have level=None."""
    out: list[_FlatBlock] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.type == "heading_open":
            # Triple: heading_open, inline (with .content), heading_close
            level = int(t.tag[1])  # 'h2' -> 2
            text = tokens[i + 1].content
            out.append(_FlatBlock(element=MarkdownHeading(text=text, body=[]), level=level))
            i += 3
        elif t.type == "paragraph_open":
            # Triple: paragraph_open, inline (with .content), paragraph_close.
            # We MUST handle this — without it, prose inside heading bodies
            # is silently dropped. MarkdownParagraph is internal-only.
            content = tokens[i + 1].content
            out.append(_FlatBlock(element=MarkdownParagraph(content=content), level=None))
            i += 3
        elif t.type == "fence":
            lang = t.info.strip() or None
            out.append(_FlatBlock(element=MarkdownCodeBlock(language=lang, content=t.content), level=None))
            i += 1
        elif t.type == "bullet_list_open":
            items, advance = _collect_list_items(tokens, i, "bullet_list_close")
            out.append(_FlatBlock(element=MarkdownBulletList(items=items), level=None))
            i += advance
        elif t.type == "ordered_list_open":
            items, advance = _collect_list_items(tokens, i, "ordered_list_close")
            out.append(_FlatBlock(element=MarkdownNumberedList(items=items), level=None))
            i += advance
        elif t.type == "table_open":
            table, advance = _collect_table(tokens, i)
            out.append(_FlatBlock(element=table, level=None))
            i += advance
        else:
            i += 1
    return out


def _collect_list_items(
    tokens: list[Token], start: int, close_type: str
) -> tuple[list[str], int]:
    items: list[str] = []
    i = start + 1
    while tokens[i].type != close_type:
        if tokens[i].type == "list_item_open":
            # the inline content is two tokens later
            items.append(tokens[i + 2].content)
        i += 1
    return items, (i - start) + 1


def _collect_table(tokens: list[Token], start: int) -> tuple[MarkdownTable, int]:
    columns: list[str] = []
    rows: list[MarkdownTableRow] = []
    i = start + 1
    in_header = False
    in_body = False
    cur_row: list[str] = []
    while tokens[i].type != "table_close":
        t = tokens[i]
        if t.type == "thead_open":
            in_header = True
        elif t.type == "thead_close":
            in_header = False
        elif t.type == "tbody_open":
            in_body = True
        elif t.type == "tbody_close":
            in_body = False
        elif t.type == "tr_open":
            cur_row = []
        elif t.type == "tr_close":
            if in_header:
                columns = cur_row
            elif in_body:
                rows.append(MarkdownTableRow(cells=cur_row))
        elif t.type in ("th_open", "td_open"):
            cur_row.append(tokens[i + 1].content)
        i += 1
    return MarkdownTable(columns=columns, rows=rows), (i - start) + 1


def _nest_headings_by_level(flat: list[_FlatBlock]) -> list[BlockElement]:
    """Second pass: turn the flat block list into a tree by nesting non-heading
    blocks (and deeper headings) inside the most recent open heading scope.
    Reads heading level from the _FlatBlock wrapper (no side-channel on the
    element model)."""
    root: list[BlockElement] = []
    stack: list[tuple[int, MarkdownHeading]] = []  # (level, heading)
    for fb in flat:
        block = fb.element
        if isinstance(block, MarkdownHeading):
            assert fb.level is not None  # heading wrappers always have level
            level = fb.level
            # Pop scopes that are at our level or deeper.
            while stack and stack[-1][0] >= level:
                stack.pop()
            target = stack[-1][1].body if stack else root
            target.append(block)
            stack.append((level, block))
        else:
            target = stack[-1][1].body if stack else root
            target.append(block)
    return root
```

- [ ] **Step 4: Run test, confirm passes**

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/_ast_normalizer.py tests/agent_foundry/markdown/test_ast_normalizer.py
git commit -m "$(cat <<'EOF'
feat(markdown): AST normalizer turns markdown-it tokens into element tree

Two-pass normalizer: pass 1 produces a flat list of typed block elements
from the markdown-it-py token stream; pass 2 nests blocks under the
appropriate heading scopes by level. Frontmatter is split off as a
separate root-only element. Recognizes all six Phase-1 element kinds.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.4.2: Projector — happy paths for `AsHeading`/`AsCodeBlock`/`AsBulletList`/`AsNumberedList`/`AsTable`

**Files:**
- Create: `src/agent_foundry/markdown/_projector.py`
- Create: `tests/agent_foundry/markdown/test_projector.py`

**Dependencies:** Tasks 1.4.1, 1.3.1 (fixture `sample_models.py` used by tests).

- [ ] **Step 1: Write failing test**

Create `tests/agent_foundry/markdown/test_projector.py`:

```python
"""Tests for the element-tree → domain-instance projector."""

from __future__ import annotations

from agent_foundry.markdown._ast_normalizer import normalize
from agent_foundry.markdown._projector import project_to_model
from tests.agent_foundry.markdown.fixtures.sample_models import (
    HeaderWithSummary,
    SimpleHeader,
)


class TestProjectToModelSimple:
    def test_simple_header_with_only_title(self):
        doc = normalize("# Hello\n")
        instance = project_to_model(doc, SimpleHeader)
        assert instance.title == "Hello"

    def test_header_with_summary_extracts_str_body(self):
        doc = normalize("# My Doc\n\n## Summary\n\nGood work.\n")
        instance = project_to_model(doc, HeaderWithSummary)
        assert instance.title == "My Doc"
        # AsHeading on str captures the heading's scoped body as raw markdown.
        assert "Good work." in instance.summary
```

- [ ] **Step 2: Run test, confirm fails** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement projector**

Create `src/agent_foundry/markdown/_projector.py`:

```python
"""Walk an element tree and construct a populated domain-model instance.

The projector reads the model class's field declarations + annotations and
locates the corresponding subtree in the element tree. Strict order: model
field order must match the order of matching elements in the document.
Unmodeled elements are skipped (passthrough).
"""

from __future__ import annotations

from typing import Annotated, get_args, get_origin

from pydantic import BaseModel

from agent_foundry.markdown._ast_normalizer import NormalizedDocument
from agent_foundry.markdown.annotations import (
    AsBulletList,
    AsCodeBlock,
    AsHeading,
    AsNumberedList,
    AsTable,
)
from agent_foundry.markdown.elements import (
    BlockElement,
    MarkdownBulletList,
    MarkdownCodeBlock,
    MarkdownHeading,
    MarkdownNumberedList,
    MarkdownParagraph,
    MarkdownTable,
)
from agent_foundry.markdown.errors import MarkdownValidationError
from agent_foundry.markdown.template_model import MarkdownDocument, MarkdownHeader


def project_to_model(
    doc: NormalizedDocument,
    model_class: type[MarkdownHeader],
) -> MarkdownHeader:
    """Project a normalized document onto a domain model instance."""

    # The top-level model's title is the document's first heading.
    if not doc.blocks or not isinstance(doc.blocks[0], MarkdownHeading):
        raise MarkdownValidationError(
            f"Expected a top-level heading at start of document for "
            f"{model_class.__name__}.title; found {type(doc.blocks[0]).__name__ if doc.blocks else 'empty document'}."
        )
    top_heading = doc.blocks[0]
    # Apply TextTemplate reverse-extraction on the title if the model's title
    # field carries one. This is a Phase 1.4 concern, not deferred to 1.5.3.
    raw_title = _extract_title_value(top_heading.text, model_class)
    instance_kwargs: dict = {"title": raw_title}

    # Frontmatter on MarkdownDocument subclasses
    if issubclass(model_class, MarkdownDocument):
        if doc.frontmatter is not None:
            fm_field_type = model_class.model_fields["frontmatter"].annotation
            # Field type is `SomeBaseModel | None`. Extract the BaseModel-subclass arg.
            fm_class = _extract_basemodel_arg(fm_field_type)
            if fm_class is not None:
                instance_kwargs["frontmatter"] = fm_class.model_validate(doc.frontmatter.parsed)

    # Body fields: walk in declaration order, picking matching elements from top_heading.body.
    body_blocks = top_heading.body
    cursor = 0
    for name, field in model_class.model_fields.items():
        if name in ("title", "frontmatter"):
            continue
        cursor, value = _project_body_field(name, field, body_blocks, cursor, model_class)
        instance_kwargs[name] = value

    return model_class(**instance_kwargs)


def _project_body_field(
    name: str,
    field: object,
    blocks: list[BlockElement],
    cursor: int,
    model_class: type,
) -> tuple[int, object]:
    """Find the next matching block(s) for this field starting at `cursor`.
    Returns (new_cursor, value)."""

    from agent_foundry.markdown.meta_validation import _get_role_annotation

    ann = _get_role_annotation(field)
    field_type = field.annotation

    # AsHeading on str — find the next heading whose text matches the field name.
    if isinstance(ann, AsHeading):
        expected_text = _snake_to_title(name)
        idx, heading = _find_next_heading(blocks, cursor, expected_text, model_class, name)
        # Body of an AsHeading-on-str is captured as raw markdown.
        body_text = _serialize_block_body(heading)
        return idx + 1, body_text

    # AsCodeBlock on str
    if isinstance(ann, AsCodeBlock):
        idx, code = _find_next_of_type(blocks, cursor, MarkdownCodeBlock, model_class, name)
        return idx + 1, code.content

    # AsBulletList on list[str]
    if isinstance(ann, AsBulletList):
        idx, bl = _find_next_of_type(blocks, cursor, MarkdownBulletList, model_class, name)
        return idx + 1, bl.items

    # AsNumberedList on list[str]
    if isinstance(ann, AsNumberedList):
        idx, nl = _find_next_of_type(blocks, cursor, MarkdownNumberedList, model_class, name)
        return idx + 1, nl.items

    # AsTable on list[BaseModel]
    if isinstance(ann, AsTable):
        idx, t = _find_next_of_type(blocks, cursor, MarkdownTable, model_class, name)
        inner = get_args(field_type)[0]
        # Strict column-name check: the document's column headers must match
        # the inner model's field names (Title Cased) in declaration order.
        # Without this check, reordered or renamed columns silently misalign.
        expected_cols = [_snake_to_title(k) for k in _field_keys(inner)]
        if t.columns != expected_cols:
            raise MarkdownValidationError(
                f"{model_class.__name__}.{name}: table column mismatch. "
                f"Expected columns {expected_cols}, found {t.columns}. "
                f"Columns must match the inner model's field names in declaration order."
            )
        rows = [
            inner.model_validate(dict(zip(_field_keys(inner), row.cells)))
            for row in t.rows
        ]
        return idx + 1, rows

    # Heading-introducing without annotation: nested MarkdownHeader or list[MarkdownHeader]
    if isinstance(field_type, type) and issubclass(field_type, MarkdownHeader):
        # Single nested header: find the next heading whose nested body matches.
        # For Phase 1 simplicity, the nested header's first heading is the title.
        idx, heading = _find_next_heading(blocks, cursor, None, model_class, name)
        sub_doc = NormalizedDocument(frontmatter=None, blocks=[heading])
        nested_instance = project_to_model(sub_doc, field_type)
        return idx + 1, nested_instance

    if get_origin(field_type) is list:
        args = get_args(field_type)
        if args and isinstance(args[0], type) and issubclass(args[0], MarkdownHeader):
            # list[MarkdownHeader-subclass]: find the wrapper heading; each child heading is one item.
            # Wrapper text is field name in Title Case unless TextTemplate annotation overrides.
            wrapper_text = _resolve_wrapper_text(name, field)
            idx, wrapper = _find_next_heading(blocks, cursor, wrapper_text, model_class, name)
            items = []
            for child in wrapper.body:
                if isinstance(child, MarkdownHeading):
                    sub_doc = NormalizedDocument(frontmatter=None, blocks=[child])
                    items.append(project_to_model(sub_doc, args[0]))
            return idx + 1, items

    # Untyped body field — skip it (passthrough)
    return cursor, None


def _find_next_heading(
    blocks: list[BlockElement],
    cursor: int,
    expected_text: str | None,
    model_class: type,
    field_name: str,
) -> tuple[int, MarkdownHeading]:
    for i in range(cursor, len(blocks)):
        b = blocks[i]
        if isinstance(b, MarkdownHeading) and (expected_text is None or b.text == expected_text):
            return i, b
    raise MarkdownValidationError(
        f"{model_class.__name__}.{field_name}: expected heading "
        f"{f'with text {expected_text!r}' if expected_text else ''} not found "
        f"after position {cursor}."
    )


def _find_next_of_type(
    blocks: list[BlockElement],
    cursor: int,
    element_type: type,
    model_class: type,
    field_name: str,
) -> tuple[int, BlockElement]:
    for i in range(cursor, len(blocks)):
        if isinstance(blocks[i], element_type):
            return i, blocks[i]
    raise MarkdownValidationError(
        f"{model_class.__name__}.{field_name}: expected {element_type.__name__} "
        f"not found after position {cursor}."
    )


def _snake_to_title(name: str) -> str:
    return " ".join(w.capitalize() for w in name.split("_"))


def _field_keys(model: type[BaseModel]) -> list[str]:
    return list(model.model_fields.keys())


def _resolve_wrapper_text(field_name: str, field: object) -> str:
    """For a list[MarkdownHeader-subclass] body field, return the wrapper
    heading text. TextTemplate annotation (literal-only, no placeholders apply)
    overrides the field-name-derived default."""
    from agent_foundry.markdown.annotations import TextTemplate
    metadata = getattr(field, "metadata", []) or []
    for m in metadata:
        if isinstance(m, TextTemplate):
            return m.template
    return _snake_to_title(field_name)


def _serialize_block_body(heading: MarkdownHeading) -> str:
    """Serialize the body of a heading (a list of blocks) back to markdown text.

    Used to reconstitute an `Annotated[str, AsHeading()]` field's value, which
    is the raw markdown content of the heading's scope. Sub-headings inside
    the body are emitted at level 2 (the conventional immediate-child level
    inside a heading) — this is good enough for round-trip semantic equivalence
    on hand-edited content and for the parsed-then-rendered cycle through
    extract_subtree (which always rebases to level 1).

    Phase 1 supports: paragraphs, code blocks, bullet/numbered lists, tables,
    and sub-headings (rendered at level 2; deeper nesting is flattened to
    level 2 as well — Phase 2 may improve this if needed).
    """
    parts: list[str] = []
    for b in heading.body:
        if isinstance(b, MarkdownParagraph):
            parts.append(b.content)
        elif isinstance(b, MarkdownHeading):
            parts.append(f"## {b.text}")
            # Recursively serialize the sub-heading's body content too.
            sub_body = _serialize_block_body(b)
            if sub_body:
                parts.append(sub_body)
        elif isinstance(b, MarkdownCodeBlock):
            lang = b.language or ""
            parts.append(f"```{lang}\n{b.content}```")
        elif isinstance(b, MarkdownBulletList):
            parts.append("\n".join(f"- {item}" for item in b.items))
        elif isinstance(b, MarkdownNumberedList):
            parts.append("\n".join(f"{i+1}. {item}" for i, item in enumerate(b.items)))
        elif isinstance(b, MarkdownTable):
            parts.append(_serialize_table(b))
    return "\n\n".join(parts).strip()


def _serialize_table(t: MarkdownTable) -> str:
    header = "| " + " | ".join(t.columns) + " |"
    sep = "|" + "|".join(["---"] * len(t.columns)) + "|"
    rows = ["| " + " | ".join(r.cells) + " |" for r in t.rows]
    return "\n".join([header, sep, *rows])


def _extract_basemodel_arg(field_type: object) -> type[BaseModel] | None:
    args = get_args(field_type)
    for a in args:
        if isinstance(a, type) and issubclass(a, BaseModel):
            return a
    return None


def _extract_title_value(heading_text: str, model_class: type[MarkdownHeader]) -> str:
    """If the model's title field has a TextTemplate annotation, extract the
    {value} portion from the actual heading text. Otherwise return the heading
    text unchanged. This makes round-trip through TextTemplate('Finding {ordinal} - {value}')
    recover 'missing tests' from '### Finding 1 - missing tests'."""
    from agent_foundry.markdown.annotations import TextTemplate

    title_field = model_class.model_fields.get("title")
    if not title_field:
        return heading_text
    for m in (title_field.metadata or []):
        if isinstance(m, TextTemplate):
            return _reverse_text_template(m.template, heading_text)
    return heading_text


def _reverse_text_template(template: str, heading_text: str) -> str:
    """Given a template like 'Finding {ordinal} - {value}' and an actual heading
    text 'Finding 1 - missing tests', return the {value} portion ('missing tests').
    Returns the heading text unchanged if no {value} placeholder. Returns the
    heading text unchanged if the template literals don't match (caller's
    Pydantic validation will surface the mismatch downstream)."""
    import re

    if "{value}" not in template:
        return heading_text
    # Build a regex from the template:
    #   - Escape literal portions
    #   - Replace escaped placeholders with capture groups
    pattern = re.escape(template)
    pattern = pattern.replace(re.escape("{value}"), r"(?P<value>.*)")
    pattern = pattern.replace(re.escape("{ordinal}"), r"\d+")
    m = re.fullmatch(pattern, heading_text)
    if not m:
        return heading_text
    return m.group("value")
```

- [ ] **Step 4: Run test, confirm passes**

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/_projector.py tests/agent_foundry/markdown/test_projector.py
git commit -m "$(cat <<'EOF'
feat(markdown): projector — element tree → domain instance

Walks model fields in declaration order, locates matching elements via
annotation rules, builds a kwargs dict, instantiates the model. Handles
title, frontmatter (on MarkdownDocument), and the five non-heading
annotations plus heading-introducing nested header / list-of-header
shapes. Strict order matching with localized error messages.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.4.3: Projector — strict-order failure messages and passthrough

**Files:**
- Modify: `tests/agent_foundry/markdown/test_projector.py`
- (Implementation already in `_projector.py` — these tests verify behavior.)

**Dependencies:** Task 1.4.2.

- [ ] **Step 1: Write failing tests**

```python
import pytest

from agent_foundry.markdown.errors import MarkdownValidationError


class TestProjectorStrictOrder:
    def test_missing_required_heading_raises(self):
        from tests.agent_foundry.markdown.fixtures.sample_models import HeaderWithSummary

        doc = normalize("# Top\n\nSome text but no Summary heading.\n")
        with pytest.raises(MarkdownValidationError, match="Summary"):
            project_to_model(doc, HeaderWithSummary)


class TestProjectorPassthrough:
    def test_extra_unmodeled_heading_is_skipped(self):
        from tests.agent_foundry.markdown.fixtures.sample_models import HeaderWithSummary

        # An extra `## Notes` heading appears between the title and Summary;
        # the projector should skip it rather than fail.
        doc = normalize(
            "# Top\n\n"
            "## Notes\n\nThis is a note.\n\n"
            "## Summary\n\nThe real summary.\n"
        )
        instance = project_to_model(doc, HeaderWithSummary)
        assert "real summary" in instance.summary
```

- [ ] **Step 2: Run tests** — passthrough may need an adjustment to skip non-matching headings. Update `_find_next_heading` to skip past non-matches when `expected_text` is given:

(Already implemented in 1.4.2's `_find_next_heading`, which loops through blocks looking for a match. If `expected_text` doesn't match, the loop continues past unmatched elements. Confirm this works.)

- [ ] **Step 3: Verify**

Run: `pdm run pytest tests/agent_foundry/markdown/test_projector.py -xvs`
Expected: all pass.

- [ ] **Step 4: Lint, format, typecheck**

- [ ] **Step 5: Commit**

```bash
git add tests/agent_foundry/markdown/test_projector.py [src/agent_foundry/markdown/_projector.py]
git commit -m "$(cat <<'EOF'
test(markdown): cover projector strict-order errors and passthrough

Strict order matching produces field-localized errors when a required
heading is missing. Unmodeled headings (e.g., ## Notes inserted between
modeled sections) are skipped rather than raising.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.4.4: `validate_markdown` glue function

**Files:**
- Create: `src/agent_foundry/markdown/parser.py`
- Create: `tests/agent_foundry/markdown/test_parser.py`

**Dependencies:** Task 1.4.3.

- [ ] **Step 1: Write failing test**

Create `tests/agent_foundry/markdown/test_parser.py`:

```python
"""End-to-end tests for the public parse-and-validate function."""

from __future__ import annotations

import pytest

from agent_foundry.markdown.errors import MarkdownValidationError
from agent_foundry.markdown.parser import validate_markdown
from agent_foundry.markdown.renderer import render_instance
from tests.agent_foundry.markdown.fixtures.sample_models import (
    HeaderWithSummary,
    Finding,
    ReviewerOutput,
    ReviewerMetadata,
)


class TestValidateMarkdown:
    def test_simple_header_with_summary_round_trip(self):
        original = HeaderWithSummary(title="Doc", summary="The work is good.")
        rendered = render_instance(original)
        parsed = validate_markdown(rendered, HeaderWithSummary)
        assert parsed.title == "Doc"
        assert "The work is good." in parsed.summary

    def test_full_reviewer_output_round_trip(self):
        original = ReviewerOutput(
            title="Review of cs7-plan4",
            frontmatter=ReviewerMetadata(change_set_name="cs7", commit_range="abc..def"),
            next_steps=["A", "B"],
            summary="Looks good.",
            findings=[
                Finding(
                    title="t1",
                    code="x = 1",
                    tags=["x"],
                    description="d",
                    rationale="r",
                ),
            ],
        )
        rendered = render_instance(original)
        parsed = validate_markdown(rendered, ReviewerOutput)
        assert parsed.title == "Review of cs7-plan4"
        assert parsed.frontmatter is not None
        assert parsed.frontmatter.change_set_name == "cs7"
        assert parsed.next_steps == ["A", "B"]
        assert len(parsed.findings) == 1
        assert parsed.findings[0].title == "t1"

    def test_invalid_markdown_raises_validation_error(self):
        # Missing title heading
        with pytest.raises(MarkdownValidationError):
            validate_markdown("just text\n", HeaderWithSummary)
```

- [ ] **Step 2: Run test, confirm fails** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement glue**

Create `src/agent_foundry/markdown/parser.py`:

```python
"""Public parse-and-validate entry point."""

from __future__ import annotations

from agent_foundry.markdown._ast_normalizer import normalize
from agent_foundry.markdown._projector import project_to_model
from agent_foundry.markdown.template_model import MarkdownHeader


def validate_markdown(
    markdown: str,
    model_class: type[MarkdownHeader],
) -> MarkdownHeader:
    """Parse the given markdown text, validate it against the template model,
    and return a populated instance. Raises MarkdownValidationError on failure
    with a field-localized message."""

    doc = normalize(markdown)
    return project_to_model(doc, model_class)
```

- [ ] **Step 4: Run test, confirm passes**

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/parser.py tests/agent_foundry/markdown/test_parser.py
git commit -m "$(cat <<'EOF'
feat(markdown): public validate_markdown function

Glue function: normalize markdown to element tree, then project to a
populated domain instance. End-to-end round-trip tests for HeaderWithSummary
and the full ReviewerOutput pass.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 1.5 — Subtree extractor

### Task 1.5.1: `extract_subtree` happy path + level rebasing

**Files:**
- Create: `src/agent_foundry/markdown/extractor.py`
- Create: `tests/agent_foundry/markdown/test_extractor.py`

**Dependencies:** Task 1.4.1 (uses the AST level-aware structure).

- [ ] **Step 1: Write failing test**

Create `tests/agent_foundry/markdown/test_extractor.py`:

```python
"""Tests for the subtree extractor."""

from __future__ import annotations

import pytest

from agent_foundry.markdown.errors import MarkdownExtractionError
from agent_foundry.markdown.extractor import extract_subtree


SAMPLE = (
    "# Top\n\n"
    "Intro text.\n\n"
    "## Findings\n\n"
    "### Finding 1 - foo\n\n"
    "#### Description\n\nFoo desc.\n\n"
    "### Finding 2 - bar\n\n"
    "#### Description\n\nBar desc.\n"
)


class TestExtractSubtree:
    def test_extract_finding_1_returns_just_that_subtree(self):
        out = extract_subtree(SAMPLE, heading_level=3, title_match="Finding 1 - foo")
        # Heading 1 (rebased from level 3 to level 1):
        assert out.startswith("# Finding 1 - foo")
        # Description should be at level 2 (rebased from 4)
        assert "## Description" in out
        # Should not contain Finding 2 content
        assert "Finding 2" not in out

    def test_no_match_raises(self):
        with pytest.raises(MarkdownExtractionError, match="not found"):
            extract_subtree(SAMPLE, heading_level=3, title_match="Finding 99")

    def test_level_rebasing_is_correct(self):
        out = extract_subtree(SAMPLE, heading_level=3, title_match="Finding 2 - bar")
        # Original Finding 2 was at level 3; should now be level 1.
        assert out.startswith("# Finding 2 - bar")
        # Original Description was at level 4; should now be level 2.
        assert "## Description" in out
```

- [ ] **Step 2: Run test, confirm fails** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement extractor**

Create `src/agent_foundry/markdown/extractor.py`:

```python
"""AST-level subtree extractor.

Locates a heading by level + exact text match, returns the heading's full scope
as a markdown string with heading levels rebased so the matched heading becomes
level 1. The result can be passed directly to validate_markdown against a
template model whose top heading is at level 1.
"""

from __future__ import annotations

from markdown_it import MarkdownIt
from markdown_it.token import Token

from agent_foundry.markdown.errors import MarkdownExtractionError


def extract_subtree(
    markdown: str,
    *,
    heading_level: int,
    title_match: str,
) -> str:
    """Return the subtree under the heading at `heading_level` whose text
    equals `title_match`. Heading levels in the result are rebased so the
    matched heading is level 1."""

    md = MarkdownIt("commonmark").enable("table")  # NOT "gfm-like" — that requires linkify-it-py
    tokens = md.parse(markdown)

    # Find the matching heading_open token.
    match_idx = _find_matching_heading(tokens, heading_level, title_match)
    if match_idx is None:
        raise MarkdownExtractionError(
            f"No heading at level {heading_level} with text {title_match!r} "
            f"found in markdown."
        )

    # Find the end of the scope: the next heading at level <= heading_level.
    end_idx = _find_scope_end(tokens, match_idx, heading_level)

    # Slice tokens, rebase levels.
    delta = heading_level - 1  # rebase: matched heading becomes level 1
    sub_tokens = _rebase_heading_levels(tokens[match_idx:end_idx], delta)

    return _render_tokens_to_markdown(sub_tokens)


def _find_matching_heading(
    tokens: list[Token], level: int, text: str
) -> int | None:
    for i, t in enumerate(tokens):
        if t.type == "heading_open" and int(t.tag[1]) == level:
            if i + 1 < len(tokens) and tokens[i + 1].content == text:
                return i
    return None


def _find_scope_end(tokens: list[Token], start: int, scope_level: int) -> int:
    # Skip the matched heading itself.
    i = start + 3  # heading_open, inline, heading_close
    while i < len(tokens):
        t = tokens[i]
        if t.type == "heading_open" and int(t.tag[1]) <= scope_level:
            return i
        i += 1
    return len(tokens)


def _rebase_heading_levels(tokens: list[Token], delta: int) -> list[Token]:
    out = []
    for t in tokens:
        if t.type in ("heading_open", "heading_close"):
            new_level = int(t.tag[1]) - delta
            new_t = Token(t.type, f"h{new_level}", t.nesting)
            new_t.markup = "#" * new_level
            new_t.content = t.content
            out.append(new_t)
        else:
            out.append(t)
    return out


def _render_tokens_to_markdown(tokens: list[Token]) -> str:
    """Re-serialize a token stream back to markdown text. For Phase 1 we use a
    minimal renderer that handles headings, paragraphs, lists, and code blocks
    cleanly enough for round-trip via validate_markdown."""

    parts: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.type == "heading_open":
            level = int(t.tag[1])
            text = tokens[i + 1].content
            parts.append(f"{'#' * level} {text}")
            i += 3
        elif t.type == "paragraph_open":
            text = tokens[i + 1].content
            parts.append(text)
            i += 3
        elif t.type == "fence":
            lang = t.info or ""
            parts.append(f"```{lang}\n{t.content}```")
            i += 1
        elif t.type == "bullet_list_open":
            i += 1
            items = []
            while tokens[i].type != "bullet_list_close":
                if tokens[i].type == "list_item_open":
                    items.append(tokens[i + 2].content)
                i += 1
            parts.append("\n".join(f"- {it}" for it in items))
            i += 1
        elif t.type == "ordered_list_open":
            i += 1
            items = []
            while tokens[i].type != "ordered_list_close":
                if tokens[i].type == "list_item_open":
                    items.append(tokens[i + 2].content)
                i += 1
            parts.append("\n".join(f"{n+1}. {it}" for n, it in enumerate(items)))
            i += 1
        else:
            i += 1
    return "\n\n".join(parts) + "\n"
```

- [ ] **Step 4: Run test, confirm passes**

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/extractor.py tests/agent_foundry/markdown/test_extractor.py
git commit -m "$(cat <<'EOF'
feat(markdown): subtree extractor with level rebasing

extract_subtree finds a heading by level + exact text match and returns
the heading's scope as markdown with heading levels rebased so the
matched heading becomes level 1. Result is directly validatable against
a template model whose top heading is at level 1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.5.2: Multiple-match detection

**Files:**
- Modify: `src/agent_foundry/markdown/extractor.py`
- Modify: `tests/agent_foundry/markdown/test_extractor.py`

**Dependencies:** Task 1.5.1.

- [ ] **Step 1: Append failing test**

```python
class TestExtractMultiMatch:
    def test_multiple_matches_raises(self):
        md = (
            "# Top\n\n"
            "## Section\n\nfirst\n\n"
            "## Section\n\nsecond\n"
        )
        with pytest.raises(MarkdownExtractionError, match="multiple"):
            extract_subtree(md, heading_level=2, title_match="Section")
```

- [ ] **Step 2: Run test, confirm fails**

- [ ] **Step 3: Update `_find_matching_heading` to detect duplicates**

```python
def _find_matching_heading(
    tokens: list[Token], level: int, text: str
) -> int | None:
    matches: list[int] = []
    for i, t in enumerate(tokens):
        if t.type == "heading_open" and int(t.tag[1]) == level:
            if i + 1 < len(tokens) and tokens[i + 1].content == text:
                matches.append(i)
    if len(matches) > 1:
        raise MarkdownExtractionError(
            f"Multiple ({len(matches)}) headings at level {level} with text "
            f"{text!r} found. extract_subtree requires a unique match in Phase 1."
        )
    return matches[0] if matches else None
```

- [ ] **Step 4: Run test, confirm passes**

- [ ] **Step 5: Lint, format, typecheck**

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/extractor.py tests/agent_foundry/markdown/test_extractor.py
git commit -m "$(cat <<'EOF'
feat(markdown): extract_subtree raises on multiple matches

Phase 1 requires a unique level + text match. Multiple matches are
ambiguous and raise MarkdownExtractionError with the count and text.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.5.3: Integration test — extract → validate against a sub-model

**Files:**
- Modify: `tests/agent_foundry/markdown/test_extractor.py`

**Dependencies:** Tasks 1.5.2, 1.4.4, 1.3.1 (fixture file).

**Note:** TextTemplate reverse-extraction (`_reverse_text_template`) was moved into Task 1.4.2 (the projector's initial implementation), since Task 1.4.4's round-trip tests require it to reach green within their own commit. This task is now a pure integration test of the extract → validate pipeline; no projector code changes are needed here.

- [ ] **Step 1: Write integration test**

```python
class TestExtractAndValidate:
    """End-to-end: extract a Finding subtree from a Reviewer document and
    validate it against the Finding model."""

    def test_extract_finding_then_validate(self):
        from agent_foundry.markdown.parser import validate_markdown
        from tests.agent_foundry.markdown.fixtures.sample_models import Finding

        # Construct a Reviewer-style document with two findings.
        md = (
            "# Review\n\n"
            "## Findings\n\n"
            "### Finding 1 - missing tests\n\n"
            "```python\nx = 1\n```\n\n"
            "- t1\n- t2\n\n"
            "#### Description\n\nNo tests.\n\n"
            "#### Rationale\n\nTDD is required.\n\n"
            "### Finding 2 - other\n\n"
            "```python\ny = 2\n```\n\n"
            "- t3\n\n"
            "#### Description\n\nOther.\n\n"
            "#### Rationale\n\nOther reason.\n"
        )
        fragment = extract_subtree(md, heading_level=3, title_match="Finding 1 - missing tests")
        finding = validate_markdown(fragment, Finding)
        # The projector's _extract_title_value reverses the TextTemplate
        # "Finding {ordinal} - {value}" against the heading text and recovers
        # the raw {value} portion: "missing tests".
        assert finding.title == "missing tests"
        assert finding.code.strip() == "x = 1"
        assert finding.tags == ["t1", "t2"]
        assert "No tests" in finding.description
```

- [ ] **Step 2: Run test, confirm passes** — should be green immediately because Task 1.4.2 already wired `_extract_title_value` and `_reverse_text_template`.

- [ ] **Step 3: Lint, format, typecheck**

- [ ] **Step 4: Commit**

```bash
git add tests/agent_foundry/markdown/test_extractor.py
git commit -m "$(cat <<'EOF'
test(markdown): extract→validate integration test for Finding subtree

End-to-end demonstration: extract a Finding subtree from a Reviewer
document with extract_subtree, then validate it against the Finding
template. TextTemplate reverse-extraction (wired in Task 1.4.2) lets the
projector recover the raw {value} portion of the heading text.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 1.6 — Round-trip property tests

### Task 1.6.1: Hand-written round-trip tests

**Files:**
- Create: `tests/agent_foundry/markdown/test_round_trip.py`

**Dependencies:** Tasks 1.4.4 (parser), 1.3.6 (renderer), 1.3.1 (fixtures).

- [ ] **Step 1: Write tests**

Create `tests/agent_foundry/markdown/test_round_trip.py`:

```python
"""Property tests: parse(render(instance)) == instance for every Phase-1 shape."""

from __future__ import annotations

from agent_foundry.markdown.parser import validate_markdown
from agent_foundry.markdown.renderer import render_instance
from tests.agent_foundry.markdown.fixtures.sample_models import (
    Finding,
    HeaderWithSummary,
    ReviewerMetadata,
    ReviewerOutput,
    SimpleHeader,
)


class TestRoundTrip:
    def test_simple_header(self):
        original = SimpleHeader(title="hello world")
        recovered = validate_markdown(render_instance(original), SimpleHeader)
        assert recovered == original

    def test_header_with_summary(self):
        original = HeaderWithSummary(title="doc title", summary="The body content here.")
        recovered = validate_markdown(render_instance(original), HeaderWithSummary)
        assert recovered.title == original.title
        assert original.summary in recovered.summary  # serialization may add whitespace

    def test_finding(self):
        original = Finding(
            title="missing tests",
            code="def foo(): pass",
            tags=["a", "b"],
            description="No tests.",
            rationale="TDD required.",
        )
        # Render at level 3 (as if inside a list at level 2)
        rendered = render_instance(original, current_level=3)
        # Need to be careful: standalone validate sees level-3 as top, but
        # parser expects level-1 top. Use extract_subtree first.
        from agent_foundry.markdown.extractor import extract_subtree
        fragment = extract_subtree(rendered, heading_level=3, title_match="Finding 1 - missing tests")
        recovered = validate_markdown(fragment, Finding)
        assert recovered.title == "missing tests"
        assert recovered.code.strip() == "def foo(): pass"
        assert recovered.tags == ["a", "b"]
        assert "No tests" in recovered.description
        assert "TDD required" in recovered.rationale

    def test_full_reviewer_output(self):
        original = ReviewerOutput(
            title="Review of foo",
            frontmatter=ReviewerMetadata(change_set_name="x", commit_range="a..b"),
            next_steps=["s1", "s2"],
            summary="Clean.",
            findings=[
                Finding(title="t1", code="c", tags=["x"], description="d", rationale="r"),
                Finding(title="t2", code="c2", tags=[], description="d2", rationale="r2"),
            ],
        )
        recovered = validate_markdown(render_instance(original), ReviewerOutput)
        assert recovered.title == original.title
        assert recovered.frontmatter == original.frontmatter
        assert recovered.next_steps == original.next_steps
        assert original.summary in recovered.summary
        assert len(recovered.findings) == 2
        assert recovered.findings[0].title == "t1"
        assert recovered.findings[1].title == "t2"

    def test_empty_findings_list_round_trips(self):
        """A reviewer document with zero findings should round-trip cleanly."""
        original = ReviewerOutput(
            title="Empty review",
            next_steps=[],
            summary="Nothing to report.",
            findings=[],
        )
        recovered = validate_markdown(render_instance(original), ReviewerOutput)
        assert recovered.findings == []
        assert recovered.title == "Empty review"

    def test_as_heading_body_with_sub_heading_round_trips(self):
        """An AsHeading-on-str body field whose value contains a sub-heading
        must survive the round-trip with sub-heading preserved (at level 2)."""

        class WithStructuredBody(MarkdownHeader):
            details: Annotated[str, AsHeading()]

        # Body of `details` contains a sub-heading and a paragraph.
        original = WithStructuredBody(
            title="Doc",
            details="## Sub-section\n\nNested content here.",
        )
        rendered = render_instance(original)
        recovered = validate_markdown(rendered, WithStructuredBody)
        # Body content survives — sub-heading text and prose both present
        assert "Sub-section" in recovered.details
        assert "Nested content here." in recovered.details
```

- [ ] **Step 2: Run tests**

- [ ] **Step 3: Iterate** — round-trip tests typically surface formatting bugs (whitespace, missing newlines) in either renderer or parser. Fix until all pass.

- [ ] **Step 4: Lint, format, typecheck**

- [ ] **Step 5: Commit**

```bash
git add tests/agent_foundry/markdown/test_round_trip.py [src/agent_foundry/markdown/...]
git commit -m "$(cat <<'EOF'
test(markdown): hand-written round-trip property tests

Verify that for every Phase-1 shape (SimpleHeader, HeaderWithSummary,
Finding, ReviewerOutput), parse(render(instance)) yields an equivalent
instance. Catches whitespace, ordering, and serialization bugs in the
renderer and parser together.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 1.7 — Public API + module-level docs

### Task 1.7.1: Public API exports

**Files:**
- Modify: `src/agent_foundry/markdown/__init__.py`

**Dependencies:** All prior tasks.

- [ ] **Step 1: Write failing test**

Add to `tests/agent_foundry/markdown/test_template_model.py` (or create a new `test_public_api.py`):

```python
class TestPublicAPI:
    """Importing from agent_foundry.markdown reaches every documented symbol."""

    def test_all_documented_symbols_importable(self):
        from agent_foundry.markdown import (
            MarkdownHeader, MarkdownDocument,
            AsHeading, AsCodeBlock, AsTable, AsBulletList, AsNumberedList, TextTemplate,
            render_template, render_instance, validate_markdown, extract_subtree,
            MarkdownTemplateError, MarkdownValidationError, MarkdownExtractionError,
        )
        # Existence of each symbol is the assertion.
        assert all([
            MarkdownHeader, MarkdownDocument,
            AsHeading, AsCodeBlock, AsTable, AsBulletList, AsNumberedList, TextTemplate,
            render_template, render_instance, validate_markdown, extract_subtree,
            MarkdownTemplateError, MarkdownValidationError, MarkdownExtractionError,
        ])
```

- [ ] **Step 2: Run test, confirm fails** — `ImportError`s for many symbols.

- [ ] **Step 3: Populate `__init__.py`**

```python
"""Declarative markdown-document machinery for Agent Foundry products.

See `agent-foundry/docs/architecture/adr_markdown_template_model_shape.md` for the
architectural decision and `archipelago/docs/plans/stage1/2026-04-17-cs7-plan4-phase1-markdown-machinery-design.md`
for the design.

Quick example:

    from agent_foundry.markdown import (
        MarkdownDocument, MarkdownHeader,
        AsHeading, TextTemplate,
        render_template, validate_markdown,
    )

    class Finding(MarkdownHeader):
        title: Annotated[str, TextTemplate("Finding {ordinal} - {value}")]
        description: Annotated[str, AsHeading()]

    class Review(MarkdownDocument):
        title: Annotated[str, TextTemplate("{value}")]
        summary: Annotated[str, AsHeading()]
        findings: list[Finding]

    template = render_template(Review)
    review = validate_markdown(produced_md, Review)
"""

from agent_foundry.markdown.annotations import (
    AsBulletList,
    AsCodeBlock,
    AsHeading,
    AsNumberedList,
    AsTable,
    TextTemplate,
)
from agent_foundry.markdown.errors import (
    MarkdownError,
    MarkdownExtractionError,
    MarkdownTemplateError,
    MarkdownValidationError,
)
from agent_foundry.markdown.extractor import extract_subtree
from agent_foundry.markdown.parser import validate_markdown
from agent_foundry.markdown.renderer import render_instance, render_template
from agent_foundry.markdown.template_model import MarkdownDocument, MarkdownHeader

__all__ = [
    # Base classes
    "MarkdownHeader",
    "MarkdownDocument",
    # Annotations
    "AsHeading",
    "AsCodeBlock",
    "AsTable",
    "AsBulletList",
    "AsNumberedList",
    "TextTemplate",
    # Engines
    "render_template",
    "render_instance",
    "validate_markdown",
    "extract_subtree",
    # Errors
    "MarkdownError",
    "MarkdownTemplateError",
    "MarkdownValidationError",
    "MarkdownExtractionError",
]
```

- [ ] **Step 4: Run test, confirm passes**

- [ ] **Step 5: Lint, format, typecheck — and run the full markdown test suite to confirm no regressions**

Run: `pdm run pytest tests/agent_foundry/markdown/ -xvs`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/markdown/__init__.py tests/agent_foundry/markdown/test_template_model.py
git commit -m "$(cat <<'EOF'
feat(markdown): public API exports for agent_foundry.markdown

Exposes the documented surface: two base classes, six annotations, four
engine functions, and four error types. Module docstring includes a
quick-start example. Element classes remain internal (importable from
.elements for advanced uses).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1.7.2: Update ADR status to "Phase 1 implemented"

**Files:**
- Modify: `docs/architecture/adr_markdown_template_model_shape.md` (in agent-foundry repo)

**Dependencies:** All prior tasks; full markdown test suite passes.

- [ ] **Step 1: Verify the suite is green**

Run: `pdm test-unit`
Expected: all passing.

- [ ] **Step 2: Update the ADR**

Edit `agent-foundry/docs/architecture/adr_markdown_template_model_shape.md`:

Change the Status section to:

```markdown
## Status

Accepted. Phase 1 implemented in `agent_foundry.markdown` (committed YYYY-MM-DD).
Subsequent phases will extend the machinery (instruction-appendix generation,
to_claude_code_schema integration, semantic validation, additional annotation types)
and build the four Archipelago agents on top.
```

Append to the Change log:

```markdown
- **YYYY-MM-DD** — Phase 1 implemented. Two base classes (`MarkdownHeader`, `MarkdownDocument`),
  six annotations, six element classes, deterministic renderer, parser/validator, subtree
  extractor. Live in `agent_foundry.markdown`. See
  `archipelago/docs/plans/stage1/2026-04-17-cs7-plan4-phase1-implementation-plan.md` for task list.
```

- [ ] **Step 3: Commit**

```bash
git add docs/architecture/adr_markdown_template_model_shape.md
git commit -m "$(cat <<'EOF'
docs(architecture): mark markdown template model ADR Phase 1 implemented

Updates Status and Change log to reflect that the Phase 1 machinery
(two base classes, six annotations, six element classes, renderer,
parser/validator, subtree extractor) is now live in agent_foundry.markdown.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Verification (Phase 1 done)

After all tasks are complete, run from the agent-foundry repo root:

- [ ] `pdm test-unit` — all unit tests pass (including the new `tests/agent_foundry/markdown/` suite).
- [ ] `pdm test-all` — all tests including integration pass.
- [ ] `pdm lint` — no ruff errors.
- [ ] `pdm format --check` — code is formatted.
- [ ] `pdm typecheck` — no pyright errors.
- [ ] Manual smoke test: open a Python REPL, import the public API, declare a small `MarkdownHeader` subclass with a few fields, render, parse a sample, extract a subtree. Verify the round-trip.

---

## Self-Review Checklist (run by the planner before handoff)

Run this checklist before declaring the plan ready for execution.

### 1. Spec coverage

- [x] Element classes: `MarkdownKind` + **7** element classes covered (Tasks 1.1.2–1.1.7; 1.1.7 adds `MarkdownParagraph` for internal AST representation).
- [x] Annotation classes: 6 annotations covered (Task 1.1.8).
- [x] Errors covered (Task 1.1.1).
- [x] `MarkdownHeader` + `MarkdownDocument` with required title and overridable frontmatter (Tasks 1.2.2, 1.2.3).
- [x] Meta-validation: 4 rules (title, body order, frontmatter, type compat — including TextTemplate clause) covered (Tasks 1.2.4–1.2.7).
- [x] Renderer (`render_template` + `render_instance`) with all 6 annotations + heading-introducing shapes + depth guard + TextTemplate wrapper override + ordinal threading (Tasks 1.3.1–1.3.7).
- [x] Parser (AST normalizer + projector + glue) covers strict-order matching, passthrough, paragraph capture, table column validation, TextTemplate reverse-extraction, all annotations (Tasks 1.4.1–1.4.4).
- [x] Subtree extractor with happy path, no-match, multi-match, and integration test (Tasks 1.5.1–1.5.3).
- [x] Round-trip property tests including empty-list and structured-body cases (Task 1.6.1).
- [x] Public API and ADR status update (Tasks 1.7.1–1.7.2).

### 2. Placeholder scan

No "TBD", "implement later", "similar to Task N", or vague references. Every code block is concrete enough to execute. Some implementation details (e.g., the awkward title-substitution-via-replace-after-render in Task 1.3.6) are flagged for the implementer to clean up during the task with a "refactor during this task" note rather than left as placeholders.

### 3. Type consistency

- `MarkdownHeader` / `MarkdownDocument` consistently spelled across all task code.
- Annotation class names match between definitions, tests, and usage in fixture models.
- Function signatures: `render_template(model_class, *, current_level=1)`, `render_instance(instance, *, current_level=1)`, `validate_markdown(markdown, model_class)`, `extract_subtree(markdown, *, heading_level, title_match)` consistent.
- `MarkdownKind` enum values match between element classes and discriminator hints.

### 4. Dependency ordering

Each task lists its prerequisites under "Dependencies." The graph is mostly linear within a sub-phase (1.1.1 → 1.1.2 → ... → 1.1.7), with cross-phase dependencies (1.3.1 needs 1.2.4 for `MarkdownHeader`; 1.4.2 needs 1.4.1 + the element classes; 1.5.3 needs 1.4.4 + 1.5.2). All dependencies are satisfiable in declaration order.

### 5. Command accuracy

- All test commands use `pdm run pytest <path> -xvs` form (verified against agent-foundry's pyproject.toml `pdm test-unit` script).
- Lint/format/typecheck commands match the agent-foundry scripts (`pdm lint`, `pdm format`, `pdm typecheck`).
- Commit messages follow `type(scope): subject` with HEREDOC and Co-Authored-By footer per the archipelago `jig.config.md` commit convention.

---

## Plan Review Swarm

After self-review, the next step per the `plan` skill is to invoke `jig:review` with mode=plan. The review swarm will scrutinize this plan before user approval.

---

## Execution Handoff

After the user approves the plan, the next step is execution. Two options:

1. **Team-Driven (parallel) — `team-dev`** — spawns implementer teammates in split panes with staggered review pipeline. Best for 3+ independent tasks touching different files.
2. **Subagent-Driven (sequential) — `sdd`** — fresh subagent per task with two-stage review after each. Best for coupled tasks or fewer than 3 tasks.

This plan has many small TDD tasks that build on each other linearly within sub-phases (each task depends on the previous one in the same sub-phase). However, sub-phases 1.1, 1.2, 1.3, and 1.5 are mostly independent of each other once their starting requirements are met. **Recommendation: `sdd` (sequential)** — given the strong inter-task dependencies within sub-phases and the value of running the full TDD cycle one task at a time with review gates.

`team-dev` could parallelize the test-fixture-creation, errors module, and elements module if you want to start sub-phases 1.1 and 1.7 in parallel — but the savings are small relative to the coordination cost.

Default: `sdd`.

---

## Change log

- **2026-04-17** — Initial implementation plan drafted from the Phase 1 design plan and the markdown-template-model ADR.
- **2026-04-17** — **Major revision after jig:review swarm.** Addressed 5 blocking + 4 major findings:
  - Replaced `MarkdownIt("gfm-like")` with `MarkdownIt("commonmark").enable("table")` in Tasks 1.4.1 and 1.5.1 (avoids missing `linkify-it-py` dep that would crash at parse time).
  - Replaced `__pydantic_extra__` side-channel in Task 1.4.1 with a `_FlatBlock` dataclass wrapper (the side-channel needs `extra="allow"` we don't want to add to the element model).
  - Added Task 1.1.7: `MarkdownParagraph` internal AST element, recognized by Task 1.4.1's `_tokens_to_blocks` paragraph-triple branch (without it, prose inside `AsHeading` body is silently dropped). Renumbered the annotation task to 1.1.8.
  - Changed Task 1.2.4's hook from `__init_subclass__` to `__pydantic_init_subclass__` (the earlier hook fires before `model_fields` includes subclass body fields, silently bypassing the body-order and type-compat rules).
  - Moved `_reverse_text_template` and the title-extraction logic from Task 1.5.3 into Task 1.4.2 (Task 1.4.4's round-trip tests need it to reach green within their own commit).
  - Added `TextTemplate` clause to the type-compat rule (Task 1.2.7) and corresponding tests; wired `TextTemplate` wrapper-text override in both renderer and projector for `list[MarkdownHeader]` fields.
  - Fixed declared dependencies: Task 1.3.1 → Task 1.2.7; Task 1.4.1 → Tasks 1.1.7, 1.2.1, 1.2.7, 1.3.1; Task 1.4.2 → Tasks 1.4.1, 1.3.1; Task 1.5.3 → Tasks 1.5.2, 1.4.4, 1.3.1; Task 1.6.1 → Tasks 1.4.4, 1.3.6, 1.3.1.
  - Added `_serialize_table` and recursive `MarkdownParagraph` handling to projector's `_serialize_block_body`.
  - Added strict column-name validation for `AsTable` projection (table columns must match the inner model's field names in declaration order).
  - Threaded `ordinal` parameter through `render_instance` (cleaner than the prior render-then-patch dance).
  - Defined standalone-render behavior for `{ordinal}` placeholder: defaults to `1` when no list parent.
  - Added empty-list and structured-AsHeading-body round-trip tests.
  - Added test for `__pydantic_init_subclass__` body-field visibility (regression test pinning the hook contract).
  - Added test coverage for `Annotated[int, TextTemplate]` title rejection, list[MarkdownHeader] body-order violations, non-optional frontmatter rejection, TextTemplate compat clauses.
  - Added cross-repo lockfile coordination step in Task 1.2.1.
  - Added typecheck-scope caveat to Conventions section.
