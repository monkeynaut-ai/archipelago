# Feature Architect Agent

## Responsibilities

- generate feature definition documents
- ensure coherence ??

considerations

- commerical (product) vs "other"

## Feature Definition Document

- feature name
- problem statement
- feature intent
- desired outcomes (user outcomes and business outcomes)
  - aspirational
- acceptance criteria
  - measurable, testable, in tension with desired outcomes (pull back towards pragmatic)
- scope boundaries (explicit statements of what is out of scope)
- assumptions
- dependencies
- constraints
- context
  - related documents, domain docs

| Field | Stance | What it does | Violation consequence |
| --- | --- | --- | --- |
| Constraints | prescriptive, boundary | Limits what the design can be | Design is wrong; must be redone |
| Assumptions | belief, unverified | States what we're betting is true about the world | Design may break at runtime; needs surfacing / testing |
| Dependencies | relational, external | Names what the design needs from outside its scope | Design can't execute at all |
