# Archipelago

An system of agents (AI, human, services, programs) for autonomous software engineering.

## Development Practices

- **Test-Driven Development (TDD)**: Write tests before implementation. Red-green-refactor cycle. All code changes must be covered by tests.
- **Trunk-Based Development**: Work directly on `main` with short-lived branches. Keep commits small and atomic. No long-lived feature branches.

## Tech Stack

- **Python 3.14**

## Project Structure

- `pyproject.toml`: Project configuration and dependencies (PDM)

## Commands

- `pdm add <package>`: Add a dependency
- `pdm run pytest`: Run tests
