# Identity Platform Admin UI Operator - AI Coding Instructions

This repository implements a Juju Charm for the [Identity Platform Admin UI](https://github.com/canonical/identity-platform-admin-ui), part of the Canonical Identity Platform. It follows the Canonical Identity Platform's standard charm architecture.

## Project Context & Architecture

- **Framework**: Python `ops` framework (Juju).
- **Target**: Kubernetes (K8s) charm.
- **Design Pattern**: **Physical Separation & Data Flow**.
  - **`src/charm.py`**: **Orchestrator**. Handles Juju events, initializes components, and coordinates data flow. Keep this file minimal.
  - **`src/services.py`**: **Business Logic**. Contains `WorkloadService` (app logic) and `PebbleService` (container management).
  - **`src/integrations.py`**: **Data Source/Sink**. Wraps relation libraries and handles data transformation for integrations (e.g., `DatabaseConfig`, `OpenFGAIntegration`).
  - **`src/configs.py`**: **Data Source**. Handles charm configuration and validation.
  - **`src/utils.py`**: Shared utilities and decorators (e.g., `container_connectivity`, `leader_unit`).

### Data Flow Pattern
Data flows from **Sources** (Config, Relations, Secrets) -> **Orchestration** (`charm.py`) -> **Sinks** (Pebble Layer, Relation Databags).
- *Do not* pass raw relation data deep into services. Validate and structure it in `integrations.py` first using `dataclass` or `Pydantic` models.
- **State Management**: Use `PeerData` in `src/integrations.py` to manage state across units (e.g., `COOKIES_ENCRYPTION_KEY`, migration versions).

## Critical Workflows

- **Pre-commit**: This project uses `pre-commit` to enforce standards.
  - **Formatting**: `tox -e fmt` (runs `isort` and `ruff format`). **Always run this before committing.**
  - **Linting**: `tox -e lint` (runs `ruff`, `codespell`, `mypy`).
- **Development Environment**: Use `tox devenv` to create the development virtual environment.
- **Unit Tests**: `tox -e unit`. Tests are in `tests/unit/`.
  - Mock `ops.model.Container` and external libraries.
- **Integration Tests**: `tox -e integration`. Tests are in `tests/integration/`.
  - Uses `pytest-operator`.
- **Build**: `charmcraft pack`.
- **Library Management**: Files in `lib/charms/` are managed by `charmcraft`. Treat them as **read-only** unless they are explicitly defined and maintained by this repository.

## Coding Conventions

- **Holistic Handler Pattern**: The charm uses a `_holistic_handler` method in `src/charm.py` to centralize reconciliation logic.
  - Most event handlers (e.g., `_on_config_changed`, `_on_pebble_ready`, `_on_peer_relation_changed`) should delegate to `_holistic_handler`.
  - This handler checks preconditions (using `NOOP_CONDITIONS` and `EVENT_DEFER_CONDITIONS`), manages secrets, updates relations, and plans the Pebble layer.
  - **Status Management**: Unit status is handled separately in `_on_collect_status` (Juju `collect-unit-status` hook), which evaluates the overall state of the charm.
- **Event Handling**: Limit the use of `event.defer()` as much as possible. Prefer the holistic handler pattern to reconcile state based on current conditions.
- **Type Hinting**: Strict typing is required. Use `typing.Optional`, `typing.List`, etc.
- **Docstrings**: Google-style docstrings for all classes and public methods.
- **Error Handling**: Use custom exceptions in `src/exceptions.py`. Catch them in `charm.py` to set unit status (e.g., `BlockedStatus`).
- **Observability**:
  - Use `charms.loki_k8s.v1.loki_push_api` for logging.
  - Use `charms.prometheus_k8s.v0.prometheus_scrape` for metrics.
  - Use `charms.tempo_k8s.v2.tracing` for tracing.
  - Use `charms.grafana_k8s.v0.grafana_dashboard` for dashboards.

## Configuration & Secrets

- **Sensitive Information**: Do not pass sensitive information (e.g., API keys, passwords) directly in charm config. Use **Juju Secrets**.
- **Resource Management**: Use `KubernetesComputeResourcesPatch` (from `charms.observability_libs.v0.kubernetes_compute_resources_patch`) to handle `cpu` and `memory` configurations.

## Integration Points

- **Database**: `pg-database` (PostgreSQL) - managed via `DatabaseRequires` and `DatabaseConfig`.
- **Identity**: `hydra-endpoint-info`, `kratos-info`, `openfga`, `oauth`.
- **Ingress**: `ingress` (Traefik) - managed via `IngressPerAppRequirer`.
- **Certificates**: `receive-ca-cert` - managed via `CertificateTransferRequires`.
- **SMTP**: `smtp` - managed via `SmtpRequires`.

## Database Migrations

- **Actions**: The charm implements `run-migration-up`, `run-migration-down`, and `run-migration-status` actions.
- **Logic**: Migration logic resides in `src/charm.py` (action handlers) and `src/services.py` (CLI execution).
- **State**: Migration version is tracked in peer relation data (`PeerData`).

## Debugging Deployments

When debugging deployment issues, follow this structured approach. **Note**: The MCP server tools are preferred for their integration, but if the MCP server is unavailable, use the standard CLI commands provided as alternatives.

1. **Check Model Status**: Use the MCP server (`get_status`) or `juju status` to identify blocked or waiting units.
   - Look for status messages indicating missing dependencies or check failures (e.g., "Migration check failed").
2. **Inspect Juju Logs**: Use the MCP server (`get_debug_log`) or `juju debug-log` to find specific error messages from the charm code.
   - Look for Python exceptions or non-zero exit codes from subprocess calls.
3. **Inspect Workload Logs**: Use the MCP server (`get_workload_logs`) or `kubectl logs` (via terminal) to check the application's standard output/error.
   - This helps identify application startup issues that the charm might not catch immediately.
4. **Verify Workload Environment**: Use `kubectl exec` to run commands inside the container.
   - Verify the application version (`<app-binary> version`).
   - Verify available commands (`<app-binary> --help`).
   - Check for missing files or permissions.

## Continuous Improvement

- **Instruction Maintenance**: As you work on the codebase, if you identify new patterns, best practices, or recurring issues that are not covered here, **you must update this file**. This ensures that the instructions remain relevant and helpful for future tasks.
