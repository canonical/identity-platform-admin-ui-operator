# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import json
from unittest.mock import MagicMock

import pytest
from conftest import create_state
from ops.testing import ActionFailed, Container, Context, State
from pytest_mock import MockerFixture

from constants import PEER_INTEGRATION_NAME, WORKLOAD_CONTAINER
from exceptions import MigrationError


@pytest.fixture
def mocked_workload_service(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.WorkloadService", autospec=True)


@pytest.fixture
def mocked_cli(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.CommandLine", autospec=True)


@pytest.fixture
def mocked_database_config(mocker: MockerFixture) -> MagicMock:
    mock = mocker.patch("charm.DatabaseConfig")
    mock.load.return_value.migration_version = "migration_version_0"
    mock.load.return_value.dsn = "postgres://postgres:password@localhost:5432/db"
    return mock


class TestCreateIdentityAction:
    def test_create_identity_failed(
        self, context: Context, mocked_cli: MagicMock, mocked_workload_service: MagicMock
    ) -> None:
        state = create_state()

        mocked_cli.return_value.create_identity.return_value = None
        params = {
            "schema": "some-schema",
            "traits": {"email": "my@email.com"},
            "password": "password",
        }

        with pytest.raises(ActionFailed):
            context.run(context.on.action("create-identity", params=params), state)

    def test_create_identity_success(
        self,
        context: Context,
        mocked_cli: MagicMock,
        mocked_workload_service: MagicMock,
        all_satisfied_conditions,
    ) -> None:
        state = create_state()

        mocked_cli.return_value.create_identity.return_value = "identity-id"
        params = {
            "schema": "some-schema",
            "traits": {"email": "my@email.com"},
            "password": "password",
        }

        context.run(context.on.action("create-identity", params=params), state)

        mocked_cli.return_value.create_identity.assert_called_with(
            {"email": "my@email.com"}, schema_id="some-schema", password="password"
        )


class TestRunMigrationUpAction:
    def test_when_not_leader_unit(self, context: Context) -> None:
        state = create_state(leader=False)
        with pytest.raises(ActionFailed, match="Non-leader unit cannot run migration action"):
            context.run(context.on.action("run-migration-up"), state)

    def test_when_service_not_ready(
        self, context: Context, mocked_workload_service: MagicMock
    ) -> None:
        state = create_state()
        mocked_workload_service.return_value.is_running.return_value = False

        with pytest.raises(ActionFailed, match="Service is not ready"):
            context.run(context.on.action("run-migration-up"), state)

    def test_when_peer_integration_not_exists(
        self, context: Context, mocked_workload_service: MagicMock
    ) -> None:
        # Create state without peer relation
        state = State(
            leader=True,
            containers=[Container(name=WORKLOAD_CONTAINER, can_connect=True)],
        )
        mocked_workload_service.return_value.is_running.return_value = True

        with pytest.raises(ActionFailed, match="Peer integration is not ready yet"):
            context.run(context.on.action("run-migration-up"), state)

    def test_when_commandline_failed(
        self,
        context: Context,
        mocked_workload_service: MagicMock,
        mocked_cli: MagicMock,
        mocked_database_config: MagicMock,
    ) -> None:
        state = create_state()
        mocked_workload_service.return_value.is_running.return_value = True
        mocked_cli.return_value.migrate_up.side_effect = MigrationError("error0")

        with pytest.raises(ActionFailed, match="Database migration up failed"):
            context.run(context.on.action("run-migration-up"), state)

    def test_when_action_succeeds(
        self,
        context: Context,
        mocked_workload_service: MagicMock,
        mocked_cli: MagicMock,
        mocked_database_config: MagicMock,
        all_satisfied_conditions,
    ) -> None:
        state = create_state()
        mocked_workload_service.return_value.is_running.return_value = True
        mocked_cli.return_value.migrate_up.return_value = None
        mocked_workload_service.return_value.version = "1.0.0"

        out = context.run(context.on.action("run-migration-up"), state)

        peer_rel_out = next(r for r in out.relations if r.endpoint == PEER_INTEGRATION_NAME)
        assert peer_rel_out.local_app_data["migration_version_0"] == json.dumps("1.0.0")


class TestRunMigrationDownAction:
    def test_when_not_leader_unit(self, context: Context) -> None:
        state = create_state(leader=False)
        with pytest.raises(ActionFailed, match="Non-leader unit cannot run migration action"):
            context.run(context.on.action("run-migration-down"), state)

    def test_when_service_not_ready(
        self, context: Context, mocked_workload_service: MagicMock
    ) -> None:
        state = create_state()
        mocked_workload_service.return_value.is_running.return_value = False

        with pytest.raises(ActionFailed, match="Service is not ready"):
            context.run(context.on.action("run-migration-down"), state)

    def test_when_peer_integration_not_exists(
        self, context: Context, mocked_workload_service: MagicMock
    ) -> None:
        # Create state without peer relation
        state = State(
            leader=True,
            containers=[Container(name=WORKLOAD_CONTAINER, can_connect=True)],
        )
        mocked_workload_service.return_value.is_running.return_value = True

        with pytest.raises(ActionFailed, match="Peer integration is not ready yet"):
            context.run(context.on.action("run-migration-down"), state)

    def test_when_commandline_failed(
        self,
        context: Context,
        mocked_workload_service: MagicMock,
        mocked_cli: MagicMock,
        mocked_database_config: MagicMock,
    ) -> None:
        state = create_state()
        mocked_workload_service.return_value.is_running.return_value = True
        mocked_cli.return_value.migrate_down.side_effect = MigrationError("error0")

        with pytest.raises(ActionFailed, match="Database migration down failed"):
            context.run(context.on.action("run-migration-down"), state)

    def test_when_action_succeeds(
        self,
        context: Context,
        mocked_workload_service: MagicMock,
        mocked_cli: MagicMock,
        mocked_database_config: MagicMock,
        all_satisfied_conditions,
    ) -> None:
        state = create_state()
        mocked_workload_service.return_value.is_running.return_value = True
        mocked_cli.return_value.migrate_down.return_value = None
        mocked_workload_service.return_value.version = "1.0.0"

        out = context.run(context.on.action("run-migration-down"), state)

        peer_rel_out = next(r for r in out.relations if r.endpoint == PEER_INTEGRATION_NAME)
        assert peer_rel_out.local_app_data["migration_version_0"] == json.dumps("1.0.0")


class TestRunMigrationStatusAction:
    def test_when_service_not_ready(
        self, context: Context, mocked_workload_service: MagicMock
    ) -> None:
        state = create_state()
        mocked_workload_service.return_value.is_running.return_value = False

        with pytest.raises(ActionFailed, match="Service is not ready"):
            context.run(context.on.action("run-migration-status"), state)

    def test_when_commandline_failed(
        self,
        context: Context,
        mocked_workload_service: MagicMock,
        mocked_cli: MagicMock,
        mocked_database_config: MagicMock,
    ) -> None:
        state = create_state()
        mocked_workload_service.return_value.is_running.return_value = True
        mocked_cli.return_value.migrate_status.return_value = None

        with pytest.raises(
            ActionFailed, match="Failed to fetch the status of all database migrations"
        ):
            context.run(context.on.action("run-migration-status"), state)

    def test_when_action_succeeds(
        self,
        context: Context,
        mocked_workload_service: MagicMock,
        mocked_cli: MagicMock,
        mocked_database_config: MagicMock,
        all_satisfied_conditions,
    ) -> None:
        state = create_state()
        mocked_workload_service.return_value.is_running.return_value = True
        mocked_cli.return_value.migrate_status.return_value = ["migration1", "migration2"]

        context.run(context.on.action("run-migration-status"), state)
