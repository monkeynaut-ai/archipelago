---
feature_slug: mcp-tools
created_at: 2026-05-04
---

# Run Observability

## Problem statement

Applications built on Agent Foundry can only use the MCP tools that are installed in the agent containers and agent harnesses that ship with Agent Foundry. This is a limitation that users cannot accept. Applications they build on Agent Foundry must allow agents to use any MCP tool.

## Feature intent

Enable any application built on Agent Foundry to specify MCP tools that its agents can use. Each agent in that application can be configured to use any of those MCP tools. When an agent runs, the LLM powering that agent will be able to call any tool the agent is configured to use.

## Desired outcomes

### User outcomes

- User can configure an application to have access to a set of MCP tools
- User can configure an agent in the applicaton to use any MCP tools the application is configured to access

### Business outcomes

- Gain the value of expanded, unlimited MCP tool use in their applications built on Agent Foundry

## Scope boundaries

- Agent Foundry will be an MCP client, not an MCP server
- Agent Foundry will have access to MCP server tools and resources. MCP server prompts are out of scope
- Agent Foundry as an MCP client will not offer sampling, roots, or elicitation to MCP servers
- Agent Foundry will support both stdio and streamable http transports for communication with MCP servers
- Agent Foundry must support authorization via credentials in the application environment
- Oauth 2 authorization is out of scope

## Assumptions

- Agent Foundry will present a unified mechanism for applications to manage MCP tool access, regardless of which LLMs, LLM harnesses, and LLM providesr the application agents use.
- Although each LLM, LLM harness, and LLM provider has unique setup requirements to use MCP tools, Agent Foundry will implement an abstraction layer for MCP tool setup, configuration, and mangement. All requests to add an MCP tool to an agent will go through this abstraction layer.

## Dependencies

- none

## Constraints

- none

## Acceptance criteria

- An application built on Agent Foundry can specify the MCP tools it wants to use
- An agent in the application can be configured to use any MCP tools the application is configure to use
- An LLM powering an agent can successfully use an MCP tool its corresponding agent is configured to use
- Applications can access from its environment credentials that autorhize an LLM/agent to use an MCP tool
- LLM running in Agent Foundry can use MCP tools over stdio transport
- LLM running in Agent Foundry can use MCP tools over streambable http transport
