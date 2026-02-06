# Identity Platform Admin UI Operator - AI Coding Instructions

This repository implements a Juju Charm for the [Identity Platform Admin UI](https://github.com/canonical/identity-platform-admin-ui). It follows the Canonical Identity Platform's standard architecture.

## Architecture & Design Patterns

- **Framework**: Python `ops` framework (Juju).
- **Pattern**: **Physical Separation & Data Flow**.
  - **`src/charm.py`**: **Orchestrator**. Handles Juju events, initializes components, and coordinates data flow. Keep this file minimal.
  - **`src/services.py`**: **Business Logic**. `WorkloadService` (app logic) and `PebbleService` (container management).
  - **`src/integrations.py`**: **Data Adaptors**. Wraps relation libraries and handles data transformation (e.g., `DatabaseConfig`, `OpenFGAIntegration`).
  - **`src/configs.py`**: **Configuration**. Handles charm configuration and validation.
- **Data Flow**: Sources (Config, Relations, Secrets) -> Orchestration (`charm.py`) -> Sinks (Pebble Layer, Relation Databags).
  - *Do not* pass raw relation data deep into services. Validate/structure it in `integrations.py` first (`dataclass`/`Pydantic`).

## Development Workflows

- **Formatting**: `tox -e fmt` (runs `isort`, `ruff`). **Always run before committing.**
- **Linting**: `tox -e lint` (runs `ruff`, `codespell`, `mypy`).
- **Unit Tests**: `tox -e unit`.
  - **Framework**: `ops.testing` (Scenario).
  - **Location**: `tests/unit/`.
  - **Pattern**: Use `ops.testing.Context` and `ops.testing.State` for proper state-transition testing.
- **Integration Tests**: `tox -e integration`.
  - **Framework**: `jubilant`.
  - **Location**: `tests/integration/`.
  - **Pattern**: Use `jubilant` fixtures for model deployment and assertions.
- **Build**: `charmcraft pack`.

## Coding Conventions

- **Holistic Handler**: The charm uses a `_holistic_handler` in `src/charm.py` to centralize reconciliation.
  - Delegates events (config/relation changes) to this handler.
  - Checks preconditions (`NOOP_CONDITIONS`), manages secrets, updates relations, and plans Pebble layer.
- **Status Management**: Unit status handled in `_on_collect_status`.
- **State Management**: Use `PeerData` in `src/integrations.py` for cross-unit state (e.g., migration versions).
- **Error Handling**: Use custom exceptions in `src/exceptions.py`. Catch in `charm.py` to set status (e.g., `BlockedStatus`).
- **Secrets**: Use Juju Secrets for sensitive info, never charm config.

## Integration Points

- **Database**: PostgreSQL (`pg-database`) via `DatabaseRequires`.
- **Identity**: `hydra-endpoint-info`, `kratos-info`, `openfga`, `oauth`.
- **Ingress**: Traefik (`ingress`) via `IngressPerAppRequirer`.
- **Certificates**: `receive-ca-cert` via `CertificateTransferRequires`.
- **Observability**: Loki (`log-proxy`), Prometheus (`metrics-endpoint`), Tempo (`tracing`).

## Database Migrations

- **Actions**: `run-migration-up`, `run-migration-down`.
- **Logic**: Handled in `src/charm.py` (actions) and `src/services.py` (CLI).
- **State**: Migration version tracked in `PeerData`.

## Debugging

1. **Model Status**: `juju status` for blocked/waiting units.
2. **Juju Logs**: `juju debug-log` for Python exceptions.
3. **Workload Logs**: `kubectl logs` for app startup issues.
4. **Environment**: `kubectl exec` to verify binary versions and files.
