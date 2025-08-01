# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from ops import ActiveStatus, BlockedStatus, StatusBase, WaitingStatus
from ops.testing import Harness
from pytest_mock import MockerFixture

from constants import (
    DATABASE_INTEGRATION_NAME,
    HYDRA_ENDPOINTS_INTEGRATION_NAME,
    INGRESS_INTEGRATION_NAME,
    KRATOS_INFO_INTEGRATION_NAME,
    OAUTH_INTEGRATION_NAME,
    OPENFGA_INTEGRATION_NAME,
    OPENFGA_MODEL_ID,
    PEER_INTEGRATION_NAME,
    SMTP_INTEGRATION_NAME,
    WORKLOAD_CONTAINER,
)
from exceptions import PebbleError
from integrations import IngressData, TLSCertificates


class TestPebbleReadyEvent:
    @patch("charm.WorkloadService.open_port")
    def test_when_event_emitted(
        self,
        mocked_open_port: MagicMock,
        harness: Harness,
        mocked_workload_service_version: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        container = harness.model.unit.get_container(WORKLOAD_CONTAINER)
        harness.charm.on.admin_ui_pebble_ready.emit(container)

        mocked_open_port.assert_called_once()
        mocked_charm_holistic_handler.assert_called_once()
        assert mocked_workload_service_version.call_count > 1, (
            "workload service version should be set"
        )
        assert mocked_workload_service_version.call_args[0] == (
            mocked_workload_service_version.return_value,
        )


class TestUpgradeCharmEvent:
    def test_non_leader_unit(
        self,
        harness: Harness,
        peer_integration: int,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.set_leader(False)
        harness.charm.on.upgrade_charm.emit()

        mocked_workload_service.create_openfga_model.assert_not_called()
        mocked_charm_holistic_handler.assert_not_called()

    def test_when_container_not_connected(
        self,
        harness: Harness,
        peer_integration: int,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, False)
        harness.charm.on.upgrade_charm.emit()

        mocked_workload_service.create_openfga_model.assert_not_called()

    def test_when_missing_peer_integration(
        self,
        harness: Harness,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.on.upgrade_charm.emit()

        mocked_workload_service.create_openfga_model.assert_not_called()
        mocked_charm_holistic_handler.assert_not_called()

    @patch("charm.OpenFGAIntegration.is_store_ready", return_value=False)
    def test_when_openfga_store_not_ready(
        self,
        mocked_openfga_store_not_ready: MagicMock,
        harness: Harness,
        peer_integration: int,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.on.upgrade_charm.emit()
        mocked_workload_service.assert_not_called()
        mocked_charm_holistic_handler.assert_not_called()

    @patch("charm.WorkloadService.create_openfga_model", return_value="model_id")
    def test_upgrade_charm_success(
        self,
        mocked_openfga_model_creation: MagicMock,
        harness: Harness,
        mocked_openfga_store_ready: MagicMock,
        mocked_workload_service_version: MagicMock,
        peer_integration: int,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.on.upgrade_charm.emit()

        mocked_openfga_model_creation.assert_called_once()
        assert harness.charm.peer_data[mocked_workload_service_version.return_value] == {
            OPENFGA_MODEL_ID: mocked_openfga_model_creation.return_value
        }
        mocked_charm_holistic_handler.assert_called_once()


class TestOpenFGAStoreCreatedEvent:
    def test_when_container_not_connected(
        self,
        harness: Harness,
        peer_integration: int,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, False)
        harness.charm.openfga_requirer.on.openfga_store_created.emit(store_id="store_id")

        mocked_workload_service.create_openfga_model.assert_not_called()
        mocked_charm_holistic_handler.assert_not_called()

    def test_when_missing_peer_integration(
        self,
        harness: Harness,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.openfga_requirer.on.openfga_store_created.emit(store_id="store_id")

        mocked_workload_service.create_openfga_model.assert_not_called()
        mocked_charm_holistic_handler.assert_not_called()

    @patch("charm.OpenFGAIntegration.is_store_ready", return_value=False)
    def test_when_openfga_store_not_ready(
        self,
        mocked_openfga_store_not_ready: MagicMock,
        harness: Harness,
        peer_integration: int,
        mocked_workload_service: MagicMock,
        mocked_workload_service_version: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.openfga_requirer.on.openfga_store_created.emit(store_id="store_id")

        mocked_workload_service.create_openfga_model.assert_not_called()
        assert not harness.charm.peer_data[mocked_workload_service_version.return_value]
        mocked_charm_holistic_handler.assert_not_called()

    def test_non_leader_unit(
        self,
        harness: Harness,
        peer_integration: int,
        mocked_openfga_store_ready: MagicMock,
        mocked_workload_service: MagicMock,
        mocked_workload_service_version: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.set_leader(False)
        harness.charm.openfga_requirer.on.openfga_store_created.emit(store_id="store_id")

        mocked_workload_service.create_openfga_model.assert_not_called()
        assert not harness.charm.peer_data[mocked_workload_service_version.return_value]
        mocked_charm_holistic_handler.assert_called_once()

    @patch("charm.WorkloadService.create_openfga_model", return_value="model_id")
    def test_openfga_created_event_success(
        self,
        mocked_openfga_model_creation: MagicMock,
        harness: Harness,
        peer_integration: int,
        mocked_openfga_store_ready: MagicMock,
        mocked_workload_service_version: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.openfga_requirer.on.openfga_store_created.emit(store_id="store_id")

        mocked_openfga_model_creation.assert_called_once()
        assert harness.charm.peer_data[mocked_workload_service_version.return_value] == {
            OPENFGA_MODEL_ID: mocked_openfga_model_creation.return_value
        }
        mocked_charm_holistic_handler.assert_called_once()


class TestOpenFGAStoreRemovedEvent:
    def test_non_leader_unit(
        self,
        harness: Harness,
        peer_integration: int,
        mocked_workload_service_version: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.peer_data[mocked_workload_service_version.return_value] = {
            OPENFGA_MODEL_ID: "model_id"
        }
        harness.set_leader(False)

        harness.charm.openfga_requirer.on.openfga_store_removed.emit()

        assert harness.charm.peer_data[mocked_workload_service_version.return_value] == {
            OPENFGA_MODEL_ID: "model_id"
        }, "Follower unit should not clean up peer data"
        mocked_charm_holistic_handler.assert_called_once()

    def test_leader_unit(
        self,
        harness: Harness,
        peer_integration: int,
        mocked_workload_service_version: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.peer_data[mocked_workload_service_version.return_value] = {
            OPENFGA_MODEL_ID: "model_id"
        }

        harness.charm.openfga_requirer.on.openfga_store_removed.emit()

        assert not harness.charm.peer_data[mocked_workload_service_version.return_value], (
            "Leader unit should clean up peer data"
        )
        mocked_charm_holistic_handler.assert_called_once()


class TestIngressReadyEvent:
    def test_non_leader_unit(
        self,
        harness: Harness,
        ingress_integration: int,
        mocked_ingress_data: IngressData,
        mocked_oauth_integration: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.set_leader(False)

        harness.charm.ingress_requirer.on.ready.emit(
            harness.model.get_relation("ingress"),
            mocked_ingress_data.url,
        )

        mocked_oauth_integration.update_oauth_client_config.assert_not_called()
        mocked_charm_holistic_handler.assert_called_once()

    def test_leader_unit(
        self,
        harness: Harness,
        ingress_integration: int,
        mocked_ingress_data: IngressData,
        mocked_oauth_integration: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.ingress_requirer.on.ready.emit(
            harness.model.get_relation("ingress"),
            mocked_ingress_data.url,
        )

        mocked_oauth_integration.update_oauth_client_config.assert_called_once_with(
            mocked_ingress_data.url
        )
        mocked_charm_holistic_handler.assert_called_once()


class TestIngressRevokedEvent:
    def test_non_leader_unit(
        self,
        harness: Harness,
        ingress_integration: int,
        mocked_ingress_data: IngressData,
        mocked_oauth_integration: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.set_leader(False)

        harness.charm.ingress_requirer.on.revoked.emit(harness.model.get_relation("ingress"))

        mocked_oauth_integration.update_oauth_client_config.assert_not_called()
        mocked_charm_holistic_handler.assert_called_once()

    def test_leader_unit(
        self,
        harness: Harness,
        ingress_integration: int,
        mocked_ingress_data: IngressData,
        mocked_oauth_integration: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.ingress_requirer.on.revoked.emit(harness.model.get_relation("ingress"))

        mocked_oauth_integration.update_oauth_client_config.assert_called_once_with(
            mocked_ingress_data.url
        )
        mocked_charm_holistic_handler.assert_called_once()


class TestOAuthInfoChangedEvent:
    def test_non_leader_unit(
        self,
        harness: Harness,
        ingress_integration: int,
        mocked_ingress_data: IngressData,
        mocked_oauth_integration: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.set_leader(False)

        harness.charm.oauth_requirer.on.oauth_info_changed.emit("client_id", "client_secret_id")

        mocked_oauth_integration.update_oauth_client_config.assert_not_called()
        mocked_charm_holistic_handler.assert_called_once()

    def test_leader_unit(
        self,
        harness: Harness,
        ingress_integration: int,
        mocked_ingress_data: IngressData,
        mocked_oauth_integration: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.oauth_requirer.on.oauth_info_changed.emit("client_id", "client_secret_id")

        mocked_oauth_integration.update_oauth_client_config.assert_called_once_with(
            mocked_ingress_data.url
        )
        mocked_charm_holistic_handler.assert_called_once()


class TestOAuthInfoRemovedEvent:
    def test_non_leader_unit(
        self,
        harness: Harness,
        ingress_integration: int,
        mocked_ingress_data: IngressData,
        mocked_oauth_integration: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.set_leader(False)

        harness.charm.oauth_requirer.on.oauth_info_removed.emit()

        mocked_oauth_integration.update_oauth_client_config.assert_not_called()
        mocked_charm_holistic_handler.assert_called_once()

    def test_leader_unit(
        self,
        harness: Harness,
        ingress_integration: int,
        mocked_ingress_data: IngressData,
        mocked_oauth_integration: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.oauth_requirer.on.oauth_info_removed.emit()

        mocked_oauth_integration.update_oauth_client_config.assert_called_once_with(
            mocked_ingress_data.url
        )
        mocked_charm_holistic_handler.assert_called_once()


class TestCertificateAvailableEvent:
    def test_certificate_available_event_success(
        self,
        harness: Harness,
        certificate_transfer_integration: int,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.certificate_transfer_requirer.on.certificate_set_updated.emit(
            {"certificate-1", "certificate-2"},
            certificate_transfer_integration,
        )

        mocked_charm_holistic_handler.assert_called_once()
        event = mocked_charm_holistic_handler.call_args.args[0]
        assert event.snapshot() == {
            "certificates": {"certificate-1", "certificate-2"},
            "relation_id": certificate_transfer_integration,
        }


class TestCertificateRemovedEvent:
    def test_certificate_removed_event_success(
        self,
        harness: Harness,
        certificate_transfer_integration: int,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.certificate_transfer_requirer.on.certificates_removed.emit(
            certificate_transfer_integration,
        )

        mocked_charm_holistic_handler.assert_called_once()


class TestDatabaseCreatedEvent:
    def test_database_created_event_success(
        self,
        harness: Harness,
        database_integration: int,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.set_leader(True)

        harness.charm.database_requirer.on.database_created.emit(
            harness.model.get_relation(DATABASE_INTEGRATION_NAME)
        )

        mocked_charm_holistic_handler.assert_called_once()


class TestDatabaseChangedEvent:
    def test_database_changed_event_success(
        self,
        harness: Harness,
        database_integration: int,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.database_requirer.on.endpoints_changed.emit(
            harness.model.get_relation(DATABASE_INTEGRATION_NAME),
        )

        mocked_charm_holistic_handler.assert_called_once()


class TestDatabaseIntegrationBrokenEvent:
    def test_database_integration_broken_event_success(
        self,
        harness: Harness,
        database_integration: int,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.on[DATABASE_INTEGRATION_NAME].relation_broken.emit(
            harness.model.get_relation(DATABASE_INTEGRATION_NAME),
        )

        mocked_charm_holistic_handler.assert_called_once()


class TestHolisticHandler:
    @pytest.fixture(autouse=True)
    def mocked_ca_bundle(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch(
            "charm.TLSCertificates.load",
            return_value=TLSCertificates(ca_bundle="mocked_ca_bundle"),
        )

    @pytest.fixture(autouse=True)
    def migration_not_needed(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch(
            "charm.IdentityPlatformAdminUIOperatorCharm.migration_needed",
            new_callable=PropertyMock,
            return_value=False,
        )

    @pytest.fixture
    def mocked_cli(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch("charm.CommandLine.migrate_up")

    def test_when_noop_condition_failed(
        self,
        harness: Harness,
        mocked_event: MagicMock,
        mocked_workload_service: MagicMock,
    ) -> None:
        with (
            patch("charm.NOOP_CONDITIONS", new=[Mock(return_value=False)]),
            patch("charm.EVENT_DEFER_CONDITIONS", new=[Mock(return_value=True)]),
        ):
            harness.charm._holistic_handler(mocked_event)

        mocked_event.defer.assert_not_called()
        mocked_workload_service.prepare_dir.assert_not_called()
        mocked_workload_service.push_ca_certs.assert_not_called()

    def test_when_event_defer_condition_failed(
        self,
        harness: Harness,
        mocked_event: MagicMock,
        mocked_workload_service: MagicMock,
    ) -> None:
        with (
            patch("charm.NOOP_CONDITIONS", new=[Mock(return_value=True)]),
            patch("charm.EVENT_DEFER_CONDITIONS", new=[Mock(return_value=False)]),
        ):
            harness.charm._holistic_handler(mocked_event)

        mocked_event.defer.assert_called()
        mocked_workload_service.prepare_dir.assert_not_called()
        mocked_workload_service.push_ca_certs.assert_not_called()

    def test_when_all_conditions_satisfied(
        self,
        mocked_ca_bundle: MagicMock,
        harness: Harness,
        mocked_event: MagicMock,
        mocked_workload_service: MagicMock,
        mocked_pebble_service: MagicMock,
    ) -> None:
        with (
            patch("charm.NOOP_CONDITIONS", new=[Mock(return_value=True)]),
            patch("charm.EVENT_DEFER_CONDITIONS", new=[Mock(return_value=True)]),
        ):
            harness.charm._holistic_handler(mocked_event)

        mocked_event.defer.assert_not_called()
        mocked_workload_service.push_ca_certs.assert_called_once_with(
            mocked_ca_bundle.return_value.ca_bundle
        )
        mocked_pebble_service.plan.assert_called_once()

    def test_when_migration_needed_non_leader_unit(
        self,
        harness: Harness,
        mocked_cli: MagicMock,
        mocked_event: MagicMock,
        mocked_pebble_service: MagicMock,
    ) -> None:
        harness.set_leader(False)

        with (
            patch(
                "charm.IdentityPlatformAdminUIOperatorCharm.migration_needed",
                new_callable=PropertyMock,
                return_value=True,
            ),
            patch("charm.NOOP_CONDITIONS", new=[Mock(return_value=True)]),
            patch("charm.EVENT_DEFER_CONDITIONS", new=[Mock(return_value=True)]),
        ):
            harness.charm._holistic_handler(mocked_event)

        mocked_event.defer.assert_called()
        mocked_cli.assert_not_called()
        mocked_pebble_service.plan.assert_not_called()

    def test_when_migration_needed_leader_unit(
        self,
        harness: Harness,
        mocked_cli: MagicMock,
        mocked_event: MagicMock,
        mocked_pebble_service: MagicMock,
    ) -> None:
        harness.set_leader(True)

        with (
            patch(
                "charm.IdentityPlatformAdminUIOperatorCharm.migration_needed",
                new_callable=PropertyMock,
                return_value=True,
            ),
            patch("charm.NOOP_CONDITIONS", new=[Mock(return_value=True)]),
            patch("charm.EVENT_DEFER_CONDITIONS", new=[Mock(return_value=True)]),
        ):
            harness.charm._holistic_handler(mocked_event)

        mocked_cli.assert_called_once()
        mocked_pebble_service.plan.assert_called_once()

    def test_when_pebble_plan_failed(
        self,
        harness: Harness,
        mocked_event: MagicMock,
    ) -> None:
        with (
            patch(
                "charm.IdentityPlatformAdminUIOperatorCharm._pebble_layer",
                new_callable=PropertyMock,
            ),
            patch("charm.PebbleService.plan", side_effect=PebbleError),
            patch("charm.NOOP_CONDITIONS", new=[Mock(return_value=True)]),
            patch("charm.EVENT_DEFER_CONDITIONS", new=[Mock(return_value=True)]),
            pytest.raises(PebbleError),
        ):
            harness.charm._holistic_handler(mocked_event)


class TestCollectStatusEvent:
    def test_when_all_condition_satisfied(
        self,
        harness: Harness,
        all_satisfied_conditions: MagicMock,
    ) -> None:
        harness.evaluate_status()

        assert isinstance(harness.model.unit.status, ActiveStatus)

    @pytest.mark.parametrize(
        "condition, satisfied, status, message",
        [
            (
                "container_connectivity",
                False,
                WaitingStatus,
                "Container is not connected yet",
            ),
            (
                "peer_integration_exists",
                False,
                WaitingStatus,
                f"Missing integration {PEER_INTEGRATION_NAME}",
            ),
            (
                "kratos_integration_exists",
                False,
                BlockedStatus,
                f"Missing integration {KRATOS_INFO_INTEGRATION_NAME}",
            ),
            (
                "hydra_integration_exists",
                False,
                BlockedStatus,
                f"Missing integration {HYDRA_ENDPOINTS_INTEGRATION_NAME}",
            ),
            (
                "oauth_integration_exists",
                False,
                BlockedStatus,
                f"Missing integration {OAUTH_INTEGRATION_NAME}",
            ),
            (
                "openfga_integration_exists",
                False,
                BlockedStatus,
                f"Missing integration {OPENFGA_INTEGRATION_NAME}",
            ),
            (
                "ingress_integration_exists",
                False,
                BlockedStatus,
                f"Missing integration {INGRESS_INTEGRATION_NAME}",
            ),
            (
                "ca_certificate_exists",
                False,
                BlockedStatus,
                "Missing certificate transfer integration with oauth provider",
            ),
            (
                "smtp_integration_exists",
                False,
                BlockedStatus,
                f"Missing integration {SMTP_INTEGRATION_NAME}",
            ),
            (
                "database_integration_exists",
                False,
                BlockedStatus,
                f"Missing integration {DATABASE_INTEGRATION_NAME}",
            ),
            (
                "migration_needed_on_leader",
                True,
                BlockedStatus,
                "Either Database migration is required, or the migration job has failed. Please check juju logs",
            ),
            (
                "migration_needed_on_non_leader",
                True,
                WaitingStatus,
                "Waiting for leader unit to run the migration",
            ),
            (
                "openfga_store_readiness",
                False,
                WaitingStatus,
                "OpenFGA store is not ready yet",
            ),
            (
                "openfga_model_readiness",
                False,
                WaitingStatus,
                "OpenFGA model is not ready yet. If this persists, check `juju logs` for errors",
            ),
        ],
    )
    def test_when_a_condition_failed(
        self,
        harness: Harness,
        all_satisfied_conditions: MagicMock,
        mocked_pebble_service: MagicMock,
        condition: str,
        satisfied: bool,
        status: StatusBase,
        message: str,
    ) -> None:
        with patch(f"charm.{condition}", return_value=satisfied):
            harness.evaluate_status()

        assert isinstance(harness.model.unit.status, status)
        assert harness.model.unit.status.message == message
