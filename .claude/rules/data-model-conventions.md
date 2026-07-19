---
paths:
  - "**/*.py"
---

# Data Model Conventions

When designing or modifying Pydantic models, follow these rules:

- **Enumerated values** → `StrEnum` if code branches on the value;
  free `str` with suggested taxonomy in the field description if the
  value is only displayed or logged. Decision rule: "Does any code
  branch on this value?"
- **`Literal` is forbidden** for enumerated values. `StrEnum` members
  are first-class symbols that LSP operations (`findReferences`,
  `goToDefinition`, `rename`, `workspaceSymbol`) can navigate; `Literal`
  string values are not symbols and are invisible to LSP navigation.
  An agent following the LSP-first rule cannot distinguish "genuinely
  unused" from "LSP can't see it" when a routing value is a `Literal`.
  Only allowed fallback: discriminator tags on tagged unions when the
  pinned Pydantic version rejects `StrEnum`-typed discriminator fields —
  in that case write `kind: Literal[SomeEnum.VARIANT] = SomeEnum.VARIANT`.
- **Discriminated unions** use tagged wrapper types with a `kind:
  SomeEnum = SomeEnum.VARIANT` field and
  `Annotated[Union[...], Field(discriminator="kind")]`. Don't rely
  on Pydantic's smart-union field-uniqueness matching.
- **Agent boundaries** use JSON schema injection — role handlers
  inject `Model.model_json_schema()` into the agent prompt; never
  hand-enumerate valid values in role markdown.
- **Every boundary type is a Pydantic `BaseModel`** — runtime
  validation, schema generation, JSON round-trip. Plain dataclasses
  only for internal, non-serialized types.
