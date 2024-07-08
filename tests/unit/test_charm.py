# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

from unittest.mock import MagicMock, patch

from ops.model import WaitingStatus
from ops.testing import Harness

from constants import WORKLOAD_CONTAINER
from integrations import IngressData


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
        assert (
            mocked_workload_service_version.call_count > 1
        ), "workload service version should be set"
        assert mocked_workload_service_version.call_args[0] == (
            mocked_workload_service_version.return_value,
        )


class TestUpgradeCharmEvent:
    def test_non_leader_unit(
        self, harness: Harness, peer_integration: int, mocked_workload_service: MagicMock
    ) -> None:
        harness.set_leader(False)
        harness.charm.on.upgrade_charm.emit()

        mocked_workload_service.create_openfga_model.assert_not_called()

    def test_when_container_not_connected(
        self, harness: Harness, peer_integration: int, mocked_workload_service: MagicMock
    ) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, False)
        harness.charm.on.upgrade_charm.emit()

        mocked_workload_service.create_openfga_model.assert_not_called()
        assert isinstance(harness.model.unit.status, WaitingStatus)

    def test_when_missing_peer_integration(
        self, harness: Harness, mocked_workload_service: MagicMock
    ) -> None:
        harness.charm.on.upgrade_charm.emit()

        mocked_workload_service.create_openfga_model.assert_not_called()
        assert isinstance(harness.model.unit.status, WaitingStatus)

    @patch("charm.OpenFGAIntegration.is_store_ready", return_value=False)
    def test_when_openfga_store_not_ready(
        self,
        mocked_openfga_store_not_ready: MagicMock,
        harness: Harness,
        peer_integration: int,
        mocked_workload_service: MagicMock,
    ) -> None:
        harness.charm.on.upgrade_charm.emit()
        mocked_workload_service.assert_not_called()

    @patch("charm.WorkloadService.create_openfga_model", return_value="model_id")
    def test_upgrade_charm_success(
        self,
        mocked_openfga_model_creation: MagicMock,
        harness: Harness,
        mocked_openfga_store_ready: MagicMock,
        mocked_workload_service_version: MagicMock,
        peer_integration: int,
    ) -> None:
        harness.charm.on.upgrade_charm.emit()

        mocked_openfga_model_creation.assert_called_once()
        assert harness.charm.peer_data[mocked_workload_service_version.return_value] == {
            "openfga_model_id": mocked_openfga_model_creation.return_value
        }


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
        assert isinstance(harness.charm.unit.status, WaitingStatus)

    def test_when_missing_peer_integration(
        self,
        harness: Harness,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        harness.charm.openfga_requirer.on.openfga_store_created.emit(store_id="store_id")

        mocked_workload_service.create_openfga_model.assert_not_called()
        mocked_charm_holistic_handler.assert_not_called()
        assert isinstance(harness.charm.unit.status, WaitingStatus)

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
            "openfga_model_id": mocked_openfga_model_creation.return_value
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
            "openfga_model_id": "model_id"
        }
        harness.set_leader(False)

        harness.charm.openfga_requirer.on.openfga_store_removed.emit()

        assert harness.charm.peer_data[mocked_workload_service_version.return_value] == {
            "openfga_model_id": "model_id"
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
            "openfga_model_id": "model_id"
        }

        harness.charm.openfga_requirer.on.openfga_store_removed.emit()

        assert not harness.charm.peer_data[mocked_workload_service_version.return_value], (
            "Leader unit should clean " "up peer data"
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
