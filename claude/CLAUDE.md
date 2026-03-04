# CLAUDE.md

If the user asks something like "what are my options?", "ready?",  "what can we work on", etc, present them with this list
    A - implement a feature
    B - fix a bug
    C - your choice

## Session workflow
The workflow you follow depends on their choice.

### If they choose implement a feature

1. We need a feature specification with a phased plan of PRs, with each PR composed of 1 or more atomic commits
    - Ask if they have a feature specification
    - If they answer yes, ask them to copy the text of the specificationi
    - If they say no, run the spec-collaborator agent
1. Iterate over each PR in the plane in order. If the PR has commits, iterate over each commit in order
    1. Explain the objective of the commit
    2. Create a list of test names in the given/when/then format. List only test names—no code.
    3. Create the tests.
    4. Analyze existing tests for conflicts and potential changes or deletions. 
	    1. If conflicts are found, list the conflicts, suggest changes, and ask for my input.
        - First need to design implementation and refine design
    5. Implement code changes that satisfy the commit objective. Run the tests you created in step 3. Iterate over code changes and tests until all tests are green. During this step, NEVER modify any test code.
    6. Run regression tests. If there are regressions, we will discuss a plan to address them.
        - If necessary, you will implement the plan to address regressions.
    7. Ask for my approval to commit the changes.
    8. Create a NEW PR ... ?? FORMAT ?? ... ?? AGENT ??

### If they want to define features from a product compass

This workflow translates a product compass into feature definitions. Steps 1-2 run interactively in this conversation. Steps 3-4 are delegated to the feature-architect agent.

#### Step 1: Compass Intake & Analysis (interactive)

1. Ask the user to provide their product compass (or locate it if they say where it is)
2. Read and analyze the compass, then present:
   - A summary of key strategic pillars, personas, and business objectives
   - Any gaps or ambiguities that could affect feature definition quality
   - Clarifying questions about missing or unclear information
3. Wait for the user's responses. Incorporate answers and re-present the summary if it changed materially.
4. Do not proceed until the user confirms alignment on the compass understanding.

#### Step 2: Feature Identification (interactive)

1. Derive a candidate feature list by:
   - Mapping strategic pillars to user and business problems
   - Identifying capability gaps for each target persona
   - Surfacing features implied by success metrics
   - Checking for dependencies and sequencing logic
2. Present the candidate list as a numbered table (Feature Name, Primary Pillar, Problem Addressed, Target Persona)
3. Ask the user to confirm, add, remove, or adjust features
4. Iterate until the user explicitly approves the candidate list

#### Steps 3-4: Delegate to feature-architect agent

Once the candidate list is confirmed, invoke the feature-architect agent via the Task tool. The prompt MUST include:
- The confirmed candidate feature list
- The compass summary from Step 1
- The full compass text
- Any clarifications from Step 1-2 Q&A

Do NOT instruct the agent to analyze the compass or identify features — that work is already done.

### If they choose to fix a bug or an issue

1. create tests that reproduce the issue
2. implement fix until all tests are green
3. commit the fix
4. create a PR


### Otherwise

## Tool Preferences

### LSP-first rule

Before doing any of the following, use the LSP tool first — do NOT substitute Read, Grep, or Glob for these operations:

- Checking if a function/class/symbol is used anywhere → `findReferences`
- Checking what calls a function → `incomingCalls`
- Checking what a function calls → `outgoingCalls`
- Understanding a symbol's type or signature → `hover`
- Navigating to a definition → `goToDefinition`
- Finding implementations of an interface or abstract method → `goToImplementation`
- Listing all symbols in a file (functions, classes, variables) → `documentSymbol`
- Searching for symbols across the workspace by name → `workspaceSymbol`
- Getting the call hierarchy item at a position → `prepareCallHierarchy`

Only fall back to Grep/Read when LSP has no server for the file type.

### Code analysis checklist

When analyzing code for gaps, bugs, or dead code:

1. Use LSP `findReferences` to verify call sites before declaring anything unused
2. Use LSP `incomingCalls`/`outgoingCalls` to trace integration points
3. Use LSP `hover` to confirm type relationships and signatures
4. Use LSP `documentSymbol` to inventory a module's public API
5. Use LSP `workspaceSymbol` to locate symbols by name across the codebase

## Bash usage
Each Bash tool call executes in a fresh shell — no environment variables, working directory
changes, or shell state carry over between calls. This means `&&` chaining is only necessary
when commands share shell state (cd, export, source). Avoid chaining because Claude Code's
permission system evaluates the entire compound command as one string, which causes permission
prompts even when each individual command is already allowed.

- **Never chain with `&&`** — run commands as separate tool calls instead
- **Use absolute paths** instead of `cd` to set working directory
- **Use inline env vars** (e.g., `DATABASE_URL=x npx prisma migrate deploy`) instead of `source .env && ...`
- **Use tool-specific path args** (e.g., `--schema=/absolute/path`) when available
- **Run independent commands in parallel** using multiple tool calls in one message
- **Run dependent commands sequentially** as separate tool calls

## Agent Usage

### Review Agent

The prompt you pass to a review agent depends on how the agent is invoked:
    - if a user invokes an agent without instructions or requests, you must then invoke the agent with an empty prompt
    - if a user invokes an agent with instructions or requests, you must then invoke the agent with a prompt that conveys those instructions and requests
    - otherwise, you invoke the review agent with a prompt that conveys the reason you are invoking the review agent
