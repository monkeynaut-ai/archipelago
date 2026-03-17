# Lessons Learned: Configuration

This document captures design issues found in the current configuration and logging setup, why they matter, and suggested fixes.

1. Import-time side effects in `src/config.py`
Importing `config` immediately instantiated settings, mutated environment variables, and configured logging. This means any module that imports `config` can unexpectedly alter global state, which makes import order matter and complicates testing. It also ties logging to `config` imports instead of to application startup.
Suggested fix: make `src/config.py` side-effect free and move initialization into a single explicit bootstrap function called by all entrypoints.

2. Global `settings` dependency in helpers
`get_model_for_agent_type()` read a module-level `settings` instance, forcing tests to reload the module to change configuration. This is a brittle coupling that hides dependencies and makes tests harder to reason about.
Suggested fix: use a cached `get_settings()` accessor and clear it in tests, or accept a `Settings` instance explicitly as a parameter.

3. Required `anthropic_api_key` for all imports
`Settings` required `anthropic_api_key` at import time. This fails even for workflows that do not use an LLM, and makes non-LLM commands depend on LLM configuration.
Suggested fix: make the key optional in settings and validate it only when LLM code is invoked.

4. Configuration mutating `os.environ`
`initialize_environment()` wrote settings back into `os.environ`. This creates reverse dependencies (configuration changes environment), which can surprise other libraries and tests.
Suggested fix: keep `Settings` as the source of truth and only set `os.environ` explicitly during application bootstrap, when a caller requests that behavior.

5. Logging config relies on structlog private attributes
The logging formatter used private fields like `ConsoleRenderer._columns`, which can change across structlog versions without warning.
Suggested fix: prefer public structlog APIs or build a stable custom renderer without accessing private attributes.
