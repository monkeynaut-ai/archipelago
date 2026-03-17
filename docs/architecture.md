# Archipelago

An agentic system for software engineering

## Requirements

- Define AI/LLM agents for engineering tasks ... instructions, tools, permissions
- Define specialization for these agents (e.g. coding agent that specializes in React apps)
- Define how these agents work together (e.g. orchestration, output and input data structures)
- Execute on multiple objectives in parallel (implement feature ABC, fix bug XYZ) without interference
- Have a shared memory for agents working on the same objective
- Run agents with their own private context
- A dashboard to observe and manage progress on objectives, agents, workflows
- Full auditing and observability

## Constraints

- Use SDKs of existing coding agents
Do not reinvent the work of validating and applying patches. Instead, use the SDKs for OpenAI Codex, Claude Code, and others