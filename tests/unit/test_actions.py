# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more about testing at: https://juju.is/docs/sdk/testing

from unittest.mock import MagicMock, patch

import pytest
from ops.testing import ActionFailed, Harness
from pytest_mock import MockerFixture

from exceptions import MigrationError
from integrations import DatabaseConfig


class TestCreateIdentityAction:
    def test_create_identity_failed(self, harness: Harness) -> None:
        with patch("charm.CommandLine.create_identity", return_value=None):
            try:
                harness.run_action(
                    "create-identity",
                    {
                        "traits": {"email": "test@canonical.com"},
                        "schema": "schema",
                        "password": "password",
                    },
                )
            except ActionFailed as err:
                assert "Failed to create the identity. Please check the juju logs" in err.message

    def test_create_identity_success(self, harness: Harness) -> None:
        expected = "created-identity-id"
        with patch("charm.CommandLine.create_identity", return_value=expected) as mocked_cli:
            output = harness.run_action(
                "create-identity",
                {
                    "traits": {"email": "test@canonical.com"},
                    "schema": "schema",
                    "password": "password",
                },
            )

        mocked_cli.assert_called_once()
        assert output.results["identity-id"] == expected


class TestRunMigrationUpAction:
    @pytest.fixture(autouse=True)
    def mocked_database_config(self, mocker: MockerFixture) -> DatabaseConfig:
        mocked = mocker.patch(
            "charm.DatabaseConfig.load",
            return_value=DatabaseConfig(migration_version="migration_version_0"),
        )
        return mocked.return_value

    @pytest.fixture
    def mocked_cli(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch("charm.CommandLine.migrate_up")

    def test_when_not_leader_unit(
        self,
        harness: Harness,
        mocked_workload_service: MagicMock,
        mocked_cli: MagicMock,
        peer_integration: int,
    ) -> None:
        harness.set_leader(False)
        mocked_workload_service.is_running = True

        try:
            harness.run_action("run-migration-up")
        except ActionFailed as err:
            assert "Non-leader unit cannot run migration action" in err.message

        mocked_cli.assert_not_called()

    def test_when_service_not_ready(
        self,
        harness: Harness,
        mocked_workload_service: MagicMock,
        mocked_cli: MagicMock,
        peer_integration: int,
    ) -> None:
        harness.set_leader(True)
        mocked_workload_service.is_running = False

        try:
            harness.run_action("run-migration-up")
        except ActionFailed as err:
            assert (
                "Service is not ready. Please re-run the action when the charm is active"
                in err.message
            )

        mocked_cli.assert_not_called()

    def test_when_peer_integration_not_exists(
        self,
        harness: Harness,
        mocked_workload_service: MagicMock,
        mocked_cli: MagicMock,
    ) -> None:
        harness.set_leader(True)
        mocked_workload_service.is_running = True

        try:
            harness.run_action("run-migration-up")
        except ActionFailed as err:
            assert "Peer integration is not ready yet" in err.message

        mocked_cli.assert_not_called()

    def test_when_commandline_failed(
        self,
        harness: Harness,
        mocked_workload_service: MagicMock,
        mocked_cli: MagicMock,
        peer_integration: int,
    ) -> None:
        harness.set_leader(True)
        mocked_workload_service.is_running = True

        with patch("charm.CommandLine.migrate_up", side_effect=MigrationError):
            try:
                harness.run_action("run-migration-up")
            except ActionFailed as err:
                assert "Database migration up failed" in err.message

        assert not harness.charm.peer_data["migration_version_0"]

    def test_when_action_succeeds(
        self,
        harness: Harness,
        mocked_workload_service: MagicMock,
        mocked_workload_service_version: MagicMock,
        mocked_cli: MagicMock,
        peer_integration: int,
    ) -> None:
        harness.set_leader(True)
        mocked_workload_service.version = "1.0.0"
        mocked_workload_service.is_running = True

        harness.run_action("run-migration-up")

        mocked_cli.assert_called_once()
        assert harness.charm.peer_data["migration_version_0"] == "1.0.0"


class TestRunMigrationDownAction:
    @pytest.fixture(autouse=True)
    def mocked_database_config(self, mocker: MockerFixture) -> DatabaseConfig:
        mocked = mocker.patch(
            "charm.DatabaseConfig.load",
            return_value=DatabaseConfig(migration_version="migration_version_0"),
        )
        return mocked.return_value

    @pytest.fixture
    def mocked_cli(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch("charm.CommandLine.migrate_down")

    def test_when_not_leader_unit(
        self,
        harness: Harness,
        mocked_workload_service: MagicMock,
        mocked_cli: MagicMock,
        peer_integration: int,
    ) -> None:
        harness.set_leader(False)
        mocked_workload_service.is_running = True

        try:
            harness.run_action("run-migration-down")
        except ActionFailed as err:
            assert "Non-leader unit cannot run migration action" in err.message

        mocked_cli.assert_not_called()

    def test_when_service_not_ready(
        self,
        harness: Harness,
        mocked_workload_service: MagicMock,
        mocked_cli: MagicMock,
        peer_integration: int,
    ) -> None:
        harness.set_leader(True)
        mocked_workload_service.is_running = False

        try:
            harness.run_action("run-migration-down")
        except ActionFailed as err:
            assert (
                "Service is not ready. Please re-run the action when the charm is active"
                in err.message
            )

        mocked_cli.assert_not_called()

    def test_when_peer_integration_not_exists(
        self,
        harness: Harness,
        mocked_workload_service: MagicMock,
        mocked_cli: MagicMock,
    ) -> None:
        harness.set_leader(True)
        mocked_workload_service.is_running = True

        try:
            harness.run_action("run-migration-down")
        except ActionFailed as err:
            assert "Peer integration is not ready yet" in err.message

        mocked_cli.assert_not_called()

    def test_when_commandline_failed(
        self,
        harness: Harness,
        mocked_workload_service: MagicMock,
        mocked_cli: MagicMock,
        peer_integration: int,
    ) -> None:
        harness.set_leader(True)
        mocked_workload_service.is_running = True

        with patch("charm.CommandLine.migrate_down", side_effect=MigrationError):
            try:
                harness.run_action("run-migration-down")
            except ActionFailed as err:
                assert "Database migration down failed" in err.message

        assert not harness.charm.peer_data["migration_version_0"]

    def test_when_action_succeeds(
        self,
        harness: Harness,
        mocked_workload_service: MagicMock,
        mocked_workload_service_version: MagicMock,
        mocked_cli: MagicMock,
        peer_integration: int,
    ) -> None:
        harness.set_leader(True)
        mocked_workload_service.version = "1.0.0"
        mocked_workload_service.is_running = True

        harness.run_action("run-migration-down")

        mocked_cli.assert_called_once()
        assert harness.charm.peer_data["migration_version_0"] == "1.0.0"


class TestRunMigrationStatusAction:
    @pytest.fixture
    def mocked_cli(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch("charm.CommandLine.migrate_status")

    def test_when_service_not_ready(
        self,
        harness: Harness,
        mocked_workload_service: MagicMock,
        mocked_cli: MagicMock,
    ) -> None:
        mocked_workload_service.is_running = False

        try:
            harness.run_action("run-migration-status")
        except ActionFailed as err:
            assert (
                "Service is not ready. Please re-run the action when the charm is active"
                in err.message
            )

        mocked_cli.assert_not_called()

    def test_when_commandline_failed(
        self,
        harness: Harness,
        mocked_workload_service: MagicMock,
    ) -> None:
        mocked_workload_service.is_running = True

        with patch("charm.CommandLine.migrate_status", return_value=None):
            try:
                harness.run_action("run-migration-status")
            except ActionFailed as err:
                assert "Failed to fetch the status of all database migrations" in err.message

    def test_when_action_succeeds(
        self,
        harness: Harness,
        mocked_workload_service: MagicMock,
        mocked_cli: MagicMock,
    ) -> None:
        mocked_workload_service.is_running = True
        mocked_cli.return_value = "status"

        output = harness.run_action("run-migration-status")

        mocked_cli.assert_called_once()
        assert output.results["status"] == "status"
