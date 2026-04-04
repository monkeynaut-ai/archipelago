# Overview

Archipelago is an autonomous software development system build on top of Agent Foundry, which is a platform for defining and running systems of AI agents. This document describes an updated design for archipelago that incorporates reviews as feedback into the system.

## Terminology

- software implementation : umbrella term for source code, api schemas, database schemas, configuration files, etc. Very important: "software implementation" excludes all tests that are used to verify the quality and correctness of a software implementation.
- correct software : software that satisfies all requirements
- high-quality software : software that conforms to all defined qualtity standards
- working session : the transformation of a need (e.g. a job specification) into correct, high-quality software
- action : a deterministic, non-AI step that executes a predefined operation. Actions do not reason or make decisions. Examples include running a linter, committing code, and submitting a PR. Calls to external systems are actions when they require no interpretation of the response.

## Constraints

The design and implementation of Archipelago is constrained by the following:

- all objectives of an agent must persue be in harmony. The system must avoid instructing any agent to perform two objectives that are in tension (e.g. writing tests and also writing source)
- Archipelago follows test-driven development; any proposed change to software must first create tests that verify the behavior desired in the proposed change including edge cases and exception handling
- this version is scoped to unit tests only. Integration and end-to-end tests are deferred to a future version
- agent containers are reused for the duration of a job specification to conserve resources and reduce latency. Containers are destroyed after the job specification is complete

## Guiding Principles

The design and implementation of Archipelago is informed by these guiding principles

- if an agent is pursuing objectives that are in tension, decompose the agent into two or more agents, each with cohesive objectives (e.g. writing unit tests and writing integration tests are cohesive objectives)
- feedback is essential to developing correct, high-quality software. Examples of feedback include design reviews, code reviews, and test results

## Data Model

### Job Specification

Specifies the requirements that define "correct" for a software transformation (e.g. a feature request) along with quality constraints. A job specification is composed of the following information:

- objective
- constraints
- assumptions
- scope
- repo url and repo ref (we assume github)
- test paths : the directories in the repo that contain test code. All other paths are considered non-test code. Used to enforce agent write permissions
- change sets : a list of Change Set objects

### Change Set

A cohesive unit of work that correlates to a pull request (PR) in github. Each change set must be deployable to production without breaking it

- intent : the purpose and motivation behind this change set
- acceptance criteria
- interface specifications (optional) : contracts this change set introduces or modifies (APIs, function signatures, data shapes, protocols)
- steps : a sequential list of steps that "tell the story" of how to implement this change set

### Change Set Step

A self-contained change that correlates to a git commit. An agent will transform this information into an "implementation task" that specifies required unit tests and changes to the implementation

- description
- acceptance criteria addressed (from Change Set)

### Implementation Task

Specifies a self-contained atomic change to make in the software. An implementation task is ephemeral — once committed, the system disregards it for subsequent work. Origin is tracked for observability and system improvement.

- origin : the Change Set Step or Review Finding that prompted this task
- unit test changes : a list of unit tests to add and unit tests to remove. Each test must be mapped to the acceptance criteria it verifies
- implementation_change : describes the software change needed to make the added unit tests green

### Review Finding

A specific issue identified during a review of change set commits.

- description : what the issue is
- severity : must-fix-before-PR or can-defer
- category : the type of issue (e.g. design quality, code quality, test complexity, naming)
- affected files and locations : where in the code the issue exists
- suggested resolution : what should change to address the issue
- source commit hashes : which commits introduced the issue

## Agent Definitions

### Planner Agent

Analyzes the repository and step context to produce an Implementation Task. Must map each unit test in the Implementation Task to the acceptance criteria it verifies.

- inputs: Change Set Step, Change Set (for acceptance criteria context), Job Specification (for constraints and scope), current repo state
- outputs: Implementation Task (with tests mapped to acceptance criteria)
- context: preserved across invocations within a change set
- repo access: read-only

### Test Agent

Adds and removes unit tests per the Implementation Task.

- inputs: Implementation Task
- outputs: modified test files
- context: cleared between invocations
- repo access: read all, write test paths only

### Implementer Agent

Modifies the software implementation to make all tests green. Must continue working until all tests pass and all linting and formatting issues are resolved. A timeout (configured via Agent Foundry) guards against infinite loops; if the timeout fires, the system escalates to a human with the current state and failing tests.

- inputs: Implementation Task (specifically the implementation_change), current repo state (including newly modified tests)
- outputs: modified software implementation files (passing all tests, linting, and formatting)
- context: cleared between invocations
- repo access: read all, write non-test paths only

### Reviewer Agent

Reviews change set commits for coding quality, design quality, and test complexity. After a PR is submitted, triages deferred findings by time horizon.

- inputs: set of commit hashes for the change set, Job Specification (for quality constraints)
- outputs: Review Findings divided into (1) must-fix before PR and (2) can-defer after PR. For deferred findings, further divides into (a) findings to address in remaining change sets and (b) findings to address after the job specification is complete
- context: preserved across invocations within a change set
- repo access: read-only

### Dispatcher Agent

Routes deferred review findings to appropriate destinations. Decides where findings belong based on the finding's scope, the remaining change sets' descriptions, and dependency ordering. The Dispatcher does not create steps — it classifies and routes findings to the Integrator Agent for step creation.

- inputs: can-defer Review Findings, remaining Change Sets (names, intents, steps), Job Specification (for constraints and scope)
- outputs: Dispatcher Output containing routed findings (grouped by target change set), deferred findings (for post-job report), and escalations (for human input)
- context: cleared between invocations
- repo access: read-only

Routing rules:

- if a finding fits a single remaining change set, route to that change set
- if a finding cross-cuts multiple change sets, route to each affected change set
- if a finding does not fit any remaining change set but belongs to the job specification's scope, escalate to a human and ask whether to create a new change set or defer until after the job is completed
- if a finding falls outside the job specification's scope, defer it to the post-job findings report

### Integrator Agent

Revises a change set's step sequence to coherently incorporate routed findings from the Dispatcher. This agent exists because step integration is backward-looking (incorporating findings into an existing plan) while the Planner is forward-looking (transforming steps into implementation tasks). These objectives are in tension per the guiding principle of cohesive agent objectives. The Integrator considers all routed findings for a change set in the full context of the change set's existing steps, and may insert new steps, modify existing steps, reorder steps, or remove steps to maintain coherence.

- inputs: routed findings for one change set (from Dispatcher Output), the change set's current state (intent, acceptance criteria, existing steps)
- outputs: Integrator Output containing the revised step sequence and a description of changes made (inserts, modifications, reorderings, removals with rationale)
- context: cleared between invocations
- repo access: read-only

## Control and Data Flow

A working session in Archipelago is composed of the following control and data flow

- a working session begins with a Job Specification, which is created externally and provided to Archipelago as input
- the system iterates over each change set in the job specification. Within each change set:
  - iterate over each step in the change set
  - within each step iteration
    - a planner agent analyzes the repo and generates a "implementation task" using informtion in the step along with pertinent information from the corresponding change set and job specification
    - a test agent agent adds and removes unit tests per the specification in the implementation task
    - an implementer agent modifies the software implementation to turn all tests in the repo green and to adhere to the "implementation change" described in the implementation task. If existing tests regress, the implementer agent must resolve the regressions
    - an action fixes linting and formatting issues and commits the code
  - after all steps have been implemented:
    - a reviewer agent reviews the changes contained in all commits (identified by a set of commit hashes) that have been created for this change set. The review covers all coding and design quality requirements. The review also includes a report on the complexity of all new unit tests, which we use as a signal about the quality of design. The review is divided into two groups: (1) a group of findings that must be addressed before submitting a PR, and (2) a group of findings to address after submitting a PR.
    - if the group of findings that must be addressed before submitting a PR is empty, submit the PR. Otherwise, feed these findings back into the planner agent that generates implementation tasks. Each resulting implementation task must go through the full test agent → implementer agent → action sequence to maintain TDD. The review-fix cycle may repeat up to 2 times. If must-fix findings remain after 2 cycles, the system escalates to a human with the unresolved findings and pauses the working session until the human responds.
  - after submitting the PR a reviewer agent analyzes the group of findings that could wait until the PR was submitted. This agent divides these findings into two groups: (1) findings that should be addressed in the remaining change sets, and (2) findings that should be addresses after the job specification is implemented. For each finding in the group that should be addressed in the remaining change sets, a dispatcher agent adds steps that address the finding into the appropriate change set. The system maintains an evolving set of findings that should be addressed after the job specification is implemented.
- after all change sets in the job specification are implemented, the system gnerates a report on the review findings that should be addressed after the job specification is implemented.

## Future Work

- integration and end-to-end tests
- implementation task origin analysis for system improvement feedback
- failure handling for PR submission failures (CI checks, merge conflicts, branch protection)
- failure handling for human escalation timeouts
- add a design agent that operates between Job Specification input and execution.
  - it takes sets and their high-level steps, analyzes the repo, and produces enriched steps with scope hints, dependency ordering, and interface sketches. Essentially doing the work that a senior engineer does when they look at a feature spec and mentally decompose it before handing tasks to the team. Keeps Job Specification author's burden low (describe intent, not implementation detail) while giving the Planner rich, repo-aware input.
