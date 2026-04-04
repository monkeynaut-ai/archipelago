# CLAUDE.md

## Tool Preferences

### LSP-first rule

If you need to perform any of the following operations, use the LSP tool first — do NOT substitute Read, Grep, or Glob for these operations:

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

Each Bash tool call executes in a fresh shell — no environment variables, working directory changes, or shell state carry over between calls. This means `&&` chaining is only necessary when commands share shell state (cd, export, source). Avoid chaining because Claude Code's permission system evaluates the entire compound command as one string, which causes permission prompts even when each individual command is already allowed.

- **Never chain with `&&`** — run commands as separate tool calls instead
- **Use absolute paths** instead of `cd` to set working directory
- **Use inline env vars** (e.g., `DATABASE_URL=x npx prisma migrate deploy`) instead of `source .env && ...`
- **Use tool-specific path args** (e.g., `--schema=/absolute/path`) when available
- **Run independent commands in parallel** using multiple tool calls in one message
- **Run dependent commands sequentially** as separate tool calls
