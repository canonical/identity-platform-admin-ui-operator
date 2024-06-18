# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import json
import logging
from typing import Dict, Tuple
from unittest.mock import MagicMock

import pytest
from admin_ui_cli import CommandOutputParseExceptionError
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.pebble import ExecError
from ops.testing import Harness

from constants import LOG_DIR, WORKLOAD_CONTAINER, WORKLOAD_SERVICE


def setup_peer_relation(harness: Harness) -> Tuple[int, str]:
    app_name = "identity-platform-admin-ui"
    relation_id = harness.add_relation("identity-platform-admin-ui", app_name)
    return relation_id, app_name


def setup_ingress_relation(harness: Harness) -> Tuple[int, str]:
    """Set up ingress relation."""
    relation_id = harness.add_relation("ingress", "traefik")
    harness.add_relation_unit(relation_id, "traefik/0")
    url = f"http://ingress:80/{harness.model.name}-identity-platform-admin-ui"
    harness.update_relation_data(
        relation_id,
        "traefik",
        {"ingress": json.dumps({"url": url})},
    )
    return relation_id, url


def setup_hydra_relation(harness: Harness) -> int:
    relation_id = harness.add_relation("hydra-endpoint-info", "hydra")
    harness.add_relation_unit(relation_id, "hydra/0")
    harness.update_relation_data(
        relation_id,
        "hydra",
        {
            "admin_endpoint": "http://hydra-admin-url:80/testing-hydra",
            "public_endpoint": "http://hydra-public-url:80/testing-hydra",
        },
    )
    return relation_id


def setup_kratos_relation(harness: Harness) -> int:
    relation_id = harness.add_relation("kratos-info", "kratos")
    harness.add_relation_unit(relation_id, "kratos/0")
    harness.update_relation_data(
        relation_id,
        "kratos",
        {
            "admin_endpoint": "http://kratos-admin-url:80/testing-kratos",
            "public_endpoint": "http://kratos-public-url:80/testing-kratos",
            "providers_configmap_name": "providers",
            "schemas_configmap_name": "identity-schemas",
            "configmaps_namespace": "testing",
        },
    )
    return relation_id


def setup_oathkeeper_relation(harness: Harness) -> int:
    relation_id = harness.add_relation("oathkeeper-info", "oathkeeper")
    harness.add_relation_unit(relation_id, "oathkeeper/0")
    harness.update_relation_data(
        relation_id,
        "oathkeeper",
        {
            "public_endpoint": "http://oathkeeper-url:80/testing-oathkeeper",
            "rules_configmap_name": "access-rules",
            "configmaps_namespace": "testing",
        },
    )
    return relation_id


def setup_openfga_relation(harness: Harness) -> int:
    relation_id = harness.add_relation("openfga", "openfga")
    harness.add_relation_unit(relation_id, "openfga/0")
    harness.update_relation_data(
        relation_id,
        "openfga",
        {
            "store_id": "store_id",
            "token_secret_id": "token_secret_id",
            "address": "127.0.0.1",
            "scheme": "http",
            "port": "8080",
            "dns_name": "example.domain.test.com/1234",
        },
    )
    return relation_id


def setup_loki_relation(harness: Harness) -> int:
    relation_id = harness.add_relation("logging", "loki-k8s")
    harness.add_relation_unit(relation_id, "loki-k8s/0")
    databag = {
        "promtail_binary_zip_url": json.dumps({
            "amd64": {
                "filename": "promtail-static-amd64",
                "zipsha": "543e333b0184e14015a42c3c9e9e66d2464aaa66eca48b29e185a6a18f67ab6d",
                "binsha": "17e2e271e65f793a9fbe81eab887b941e9d680abe82d5a0602888c50f5e0cac9",
                "url": "https://github.com/canonical/loki-k8s-operator/releases/download/promtail-v2.5.0/promtail-static-amd64.gz",
            }
        }),
    }
    unit_databag = {
        "endpoint": json.dumps({
            "url": "http://loki-k8s-0.loki-k8s-endpoints.cos.svc.cluster.local:3100/loki/api/v1/push"
        })
    }
    harness.update_relation_data(
        relation_id,
        "loki-k8s/0",
        unit_databag,
    )
    harness.update_relation_data(
        relation_id,
        "loki-k8s",
        databag,
    )

    return relation_id


def setup_tempo_relation(harness: Harness) -> int:
    relation_id = harness.add_relation("tracing", "tempo-k8s")
    harness.add_relation_unit(relation_id, "tempo-k8s/0")

    trace_databag = {
        "host": '"tempo-k8s-0.tempo-k8s-endpoints.namespace.svc.cluster.local"',
        "ingesters": '[{"protocol": "tempo", "port": 3200}, {"protocol": "otlp_grpc", "port": 4317}, {"protocol": "otlp_http", "port": 4318}, {"protocol": "zipkin", "port": 9411}, {"protocol": "jaeger_http_thrift", "port": 14268}, {"protocol": "jaeger_grpc", "port": 14250}]',
    }
    harness.update_relation_data(
        relation_id,
        "tempo-k8s",
        trace_databag,
    )
    return relation_id


class TestPebbleReadyEvent:
    def test_cannot_connect_on_pebble_ready(
        self, harness: Harness, mocked_version: MagicMock
    ) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, False)
        container = harness.model.unit.get_container(WORKLOAD_CONTAINER)
        harness.charm.on.admin_ui_pebble_ready.emit(container)

        assert harness.charm.unit.status == WaitingStatus(
            "Waiting to connect to admin-ui container"
        )

    def test_peer_relation_missing(self, harness: Harness) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        container = harness.model.unit.get_container(WORKLOAD_CONTAINER)
        harness.charm.on.admin_ui_pebble_ready.emit(container)

        assert harness.charm.unit.status == WaitingStatus("Waiting for peer relation")

    def test_can_connect_on_pebble_ready(
        self,
        harness: Harness,
        mocked_openfga_store_info: MagicMock,
        mocked_openfga_model_id: MagicMock,
    ) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        setup_peer_relation(harness)
        setup_openfga_relation(harness)
        container = harness.model.unit.get_container(WORKLOAD_CONTAINER)
        harness.charm.on.admin_ui_pebble_ready.emit(container)
        setup_kratos_relation(harness)
        setup_hydra_relation(harness)

        assert isinstance(harness.charm.unit.status, ActiveStatus)
        service = harness.model.unit.get_container(WORKLOAD_CONTAINER).get_service(
            WORKLOAD_SERVICE
        )
        assert service.is_running()

    def test_expected_layer(
        self,
        harness: Harness,
        mocked_hydra_url: MagicMock,
        mocked_openfga_store_info: MagicMock,
        mocked_openfga_model_id: MagicMock,
    ) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        setup_kratos_relation(harness)
        harness.charm.on.admin_ui_pebble_ready.emit(WORKLOAD_CONTAINER)

        expected_layer = {
            "summary": "Pebble Layer for Identity Platform Admin UI",
            "description": "Pebble Layer for Identity Platform Admin UI",
            "services": {
                WORKLOAD_SERVICE: {
                    "override": "replace",
                    "summary": "identity platform admin ui",
                    "command": "/usr/bin/identity-platform-admin-ui serve",
                    "startup": "enabled",
                    "environment": {
                        "AUTHORIZATION_ENABLED": True,
                        "OPENFGA_API_HOST": "127.0.0.1:8080",
                        "OPENFGA_API_SCHEME": "http",
                        "OPENFGA_API_TOKEN": "token",
                        "OPENFGA_STORE_ID": "store_id",
                        "OPENFGA_AUTHORIZATION_MODEL_ID": "01HQJMD174NPN2A4JFRFZ1NNW1",
                        "KRATOS_PUBLIC_URL": "http://kratos-public-url:80/testing-kratos",
                        "KRATOS_ADMIN_URL": "http://kratos-admin-url:80/testing-kratos",
                        "HYDRA_ADMIN_URL": "http://hydra-url.com",
                        "IDP_CONFIGMAP_NAME": "providers",
                        "IDP_CONFIGMAP_NAMESPACE": "testing",
                        "SCHEMAS_CONFIGMAP_NAME": "identity-schemas",
                        "SCHEMAS_CONFIGMAP_NAMESPACE": "testing",
                        "OATHKEEPER_PUBLIC_URL": "",
                        "RULES_CONFIGMAP_NAME": "",
                        "RULES_CONFIGMAP_NAMESPACE": "",
                        "RULES_CONFIGMAP_FILE_NAME": "admin_ui_rules.json",
                        "PORT": "8080",
                        "TRACING_ENABLED": False,
                        "LOG_LEVEL": "info",
                        "LOG_FILE": "/var/log/admin_ui.log",
                        "DEBUG": False,
                    },
                }
            },
            "checks": {
                "alive": {
                    "override": "replace",
                    "http": {"url": "http://localhost:8080/api/v0/status"},
                },
            },
        }

        assert harness.charm._admin_ui_pebble_layer.to_dict() == expected_layer

    def test_log_dir_created_on_pebble_ready(self, harness: Harness) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        setup_peer_relation(harness)
        setup_openfga_relation(harness)
        container = harness.model.unit.get_container(WORKLOAD_CONTAINER)
        harness.charm.on.admin_ui_pebble_ready.emit(container)
        setup_kratos_relation(harness)
        setup_hydra_relation(harness)

        assert container.exists(LOG_DIR)
        assert container.isdir(LOG_DIR)

    def test_workload_version_set(self, harness: Harness) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        harness.charm.on.admin_ui_pebble_ready.emit(WORKLOAD_CONTAINER)

        assert harness.get_workload_version() == "1.2.0"


class TestTracingRelation:
    def test_layer_updated_with_tracing_endpoint_info(
        self,
        harness: Harness,
        mocked_openfga_store_info: MagicMock,
        mocked_openfga_model_id: MagicMock,
    ) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        harness.charm.on.admin_ui_pebble_ready.emit(WORKLOAD_CONTAINER)
        setup_tempo_relation(harness)

        pebble_env = harness.charm._admin_ui_pebble_layer.to_dict()["services"][WORKLOAD_SERVICE][
            "environment"
        ]

        assert pebble_env["TRACING_ENABLED"]
        assert (
            pebble_env["OTEL_HTTP_ENDPOINT"]
            == "tempo-k8s-0.tempo-k8s-endpoints.namespace.svc.cluster.local:4318"
        )
        assert (
            pebble_env["OTEL_GRPC_ENDPOINT"]
            == "tempo-k8s-0.tempo-k8s-endpoints.namespace.svc.cluster.local:4317"
        )


class TestKratosRelation:
    def test_missing_required_kratos_relation(self, harness: Harness) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        setup_peer_relation(harness)
        container = harness.model.unit.get_container(WORKLOAD_CONTAINER)
        harness.charm.on.admin_ui_pebble_ready.emit(container)

        assert harness.model.unit.status == BlockedStatus("Missing required relation with kratos")

    def test_layer_updated_with_kratos_info(
        self,
        harness: Harness,
        mocked_openfga_store_info: MagicMock,
        mocked_openfga_model_id: MagicMock,
    ) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        harness.charm.on.admin_ui_pebble_ready.emit(WORKLOAD_CONTAINER)
        setup_kratos_relation(harness)

        pebble_env = harness.charm._admin_ui_pebble_layer.to_dict()["services"][WORKLOAD_SERVICE][
            "environment"
        ]

        assert pebble_env["KRATOS_ADMIN_URL"] == "http://kratos-admin-url:80/testing-kratos"
        assert pebble_env["KRATOS_PUBLIC_URL"] == "http://kratos-public-url:80/testing-kratos"
        assert pebble_env["IDP_CONFIGMAP_NAME"] == "providers"
        assert pebble_env["IDP_CONFIGMAP_NAMESPACE"] == "testing"
        assert pebble_env["SCHEMAS_CONFIGMAP_NAME"] == "identity-schemas"
        assert pebble_env["SCHEMAS_CONFIGMAP_NAMESPACE"] == "testing"


class TestHydraRelation:
    def test_missing_required_hydra_relation(self, harness: Harness) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        setup_peer_relation(harness)
        container = harness.model.unit.get_container(WORKLOAD_CONTAINER)
        harness.charm.on.admin_ui_pebble_ready.emit(container)
        setup_kratos_relation(harness)

        assert harness.model.unit.status == BlockedStatus("Missing required relation with hydra")

    def test_layer_updated_with_hydra_endpoint_info(
        self,
        harness: Harness,
        mocked_openfga_store_info: MagicMock,
        mocked_openfga_model_id: MagicMock,
    ) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        harness.charm.on.admin_ui_pebble_ready.emit(WORKLOAD_CONTAINER)
        setup_hydra_relation(harness)

        pebble_env = harness.charm._admin_ui_pebble_layer.to_dict()["services"][WORKLOAD_SERVICE][
            "environment"
        ]

        assert pebble_env["HYDRA_ADMIN_URL"] == "http://hydra-admin-url:80/testing-hydra"


class TestOathkeeperRelation:
    def test_layer_updated_with_oathkeeper_info(
        self,
        harness: Harness,
        mocked_openfga_store_info: MagicMock,
        mocked_openfga_model_id: MagicMock,
    ) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        harness.charm.on.admin_ui_pebble_ready.emit(WORKLOAD_CONTAINER)
        setup_oathkeeper_relation(harness)

        pebble_env = harness.charm._admin_ui_pebble_layer.to_dict()["services"][WORKLOAD_SERVICE][
            "environment"
        ]

        assert pebble_env["OATHKEEPER_PUBLIC_URL"] == "http://oathkeeper-url:80/testing-oathkeeper"
        assert pebble_env["RULES_CONFIGMAP_NAME"] == "access-rules"
        assert pebble_env["RULES_CONFIGMAP_NAMESPACE"] == "testing"


class TestIngressRelation:
    def test_ingress_relation_created(self, harness: Harness) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, True)

        relation_id, url = setup_ingress_relation(harness)
        assert url == "http://ingress:80/testing-identity-platform-admin-ui"

        app_data = harness.get_relation_data(relation_id, harness.charm.app)
        assert app_data == {
            "model": json.dumps(harness.model.name),
            "name": json.dumps("identity-platform-admin-ui"),
            "port": json.dumps(8080),
            "scheme": json.dumps("http"),
            "strip-prefix": json.dumps(True),
            "redirect-https": json.dumps(False),
        }

    def test_ingress_relation_revoked(
        self, harness: Harness, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO)
        harness.set_can_connect(WORKLOAD_CONTAINER, True)

        relation_id, _ = setup_ingress_relation(harness)
        caplog.clear()
        harness.remove_relation(relation_id)

        assert "This app no longer has ingress" in caplog.record_tuples[2]


class TestOpenFGARelation:
    def test_cannot_connect_on_openfga_store_created(self, harness: Harness) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, False)
        harness.charm.openfga.on.openfga_store_created.emit(store_id="store-id")

        assert harness.charm.unit.status == WaitingStatus(
            "Waiting to connect to admin-ui container"
        )

    def test_missing_required_openfga_relation(self, harness: Harness) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        setup_peer_relation(harness)
        container = harness.model.unit.get_container(WORKLOAD_CONTAINER)
        harness.charm.on.admin_ui_pebble_ready.emit(container)
        setup_kratos_relation(harness)
        setup_hydra_relation(harness)

        assert harness.model.unit.status == BlockedStatus("Missing required relation with openfga")

    def test_missing_required_openfga_relation_data(self, harness: Harness) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        setup_peer_relation(harness)
        container = harness.model.unit.get_container(WORKLOAD_CONTAINER)
        harness.charm.on.admin_ui_pebble_ready.emit(container)
        setup_openfga_relation(harness)
        setup_kratos_relation(harness)
        setup_hydra_relation(harness)

        assert harness.model.unit.status == WaitingStatus("Waiting for openfga store and model")

    def test_openfga_requirer_data_in_relation_databag(
        self, harness: Harness, openfga_requirer_databag: Dict
    ) -> None:
        relation_id = setup_openfga_relation(harness)
        relation_data = harness.get_relation_data(relation_id, harness.model.app.name)

        assert relation_data == openfga_requirer_databag

    def test_layer_updated_with_openfga_info(
        self,
        harness: Harness,
        mocked_openfga_store_info: MagicMock,
        mocked_openfga_model_id: MagicMock,
    ) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        harness.charm.on.admin_ui_pebble_ready.emit(WORKLOAD_CONTAINER)
        setup_peer_relation(harness)
        setup_openfga_relation(harness)

        pebble_env = harness.charm._admin_ui_pebble_layer.to_dict()["services"][WORKLOAD_SERVICE][
            "environment"
        ]

        assert pebble_env["AUTHORIZATION_ENABLED"] is True
        assert pebble_env["OPENFGA_STORE_ID"] == "store_id"
        assert pebble_env["OPENFGA_API_TOKEN"] == "token"
        assert pebble_env["OPENFGA_API_SCHEME"] == "http"
        assert pebble_env["OPENFGA_API_HOST"] == "127.0.0.1:8080"
        assert pebble_env["OPENFGA_AUTHORIZATION_MODEL_ID"] == "01HQJMD174NPN2A4JFRFZ1NNW1"

    def test_service_not_started_when_missing_openfga_model_id(
        self,
        harness: Harness,
        mocked_openfga_store_info: MagicMock,
        mocked_openfga_model_id: MagicMock,
    ) -> None:
        mocked_openfga_model_id.return_value = None
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        setup_peer_relation(harness)
        setup_openfga_relation(harness)
        setup_kratos_relation(harness)
        setup_hydra_relation(harness)

        assert harness.model.unit.get_container(WORKLOAD_CONTAINER).get_services() == {}


class TestUpgradeEvent:
    def test_cannot_connect_on_upgrade_charm(self, harness: Harness) -> None:
        harness.set_can_connect(WORKLOAD_CONTAINER, False)
        harness.charm.on.upgrade_charm.emit()

        assert harness.charm.unit.status == WaitingStatus(
            "Waiting to connect to admin-ui container"
        )

    def test_upgrade_charm_event(
        self,
        harness: Harness,
        mocked_openfga_store_info: MagicMock,
        mocked_openfga_model_id: MagicMock,
        mocked_handle_status_update_config: MagicMock,
    ) -> None:
        """Test the event emission sequence on upgrade-charm.

        Ensure that authorization is still enabled.
        """
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        setup_peer_relation(harness)
        setup_openfga_relation(harness)
        setup_kratos_relation(harness)
        setup_hydra_relation(harness)

        harness.charm.on.upgrade_charm.emit()

        mocked_handle_status_update_config.assert_called()

        pebble_env = harness.charm._admin_ui_pebble_layer.to_dict()["services"][WORKLOAD_SERVICE][
            "environment"
        ]
        assert pebble_env["AUTHORIZATION_ENABLED"] is True


class TestAdminUICLI:
    def test_model_creation_exec_error(
        self,
        harness: Harness,
        mocked_create_model: MagicMock,
        caplog: pytest.LogCaptureFixture,
        mocked_openfga_store_info: MagicMock,
    ) -> None:
        caplog.set_level(logging.ERROR)
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        setup_peer_relation(harness)
        setup_openfga_relation(harness)

        cmd = [
            "identity-platform-admin-ui",
            "create-fga-model",
            "--fga-api-url",
            "http://some-url",
            "--fga-api-token",
            "token",
            "--fga-store-id",
            "store-id",
        ]
        err = ExecError(command=cmd, exit_code=1, stdout="Out", stderr="Error")
        mocked_create_model.side_effect = err

        harness.charm.openfga.on.openfga_store_created.emit(store_id="store-id")

        error_messages = [record[2] for record in caplog.record_tuples]
        assert f"Exited with code: {err.exit_code}. Stderr: {err.stderr}" in error_messages

    def test_model_creation_parse_exception(
        self,
        harness: Harness,
        mocked_create_model: MagicMock,
        caplog: pytest.LogCaptureFixture,
        mocked_openfga_store_info: MagicMock,
    ) -> None:
        caplog.set_level(logging.ERROR)
        harness.set_can_connect(WORKLOAD_CONTAINER, True)
        setup_peer_relation(harness)
        setup_openfga_relation(harness)

        e = CommandOutputParseExceptionError("Failed to parse the command output")
        mocked_create_model.side_effect = e

        harness.charm.openfga.on.openfga_store_created.emit(store_id="store-id")

        error_messages = [record[2] for record in caplog.record_tuples]
        assert f"Failed to get the model id: {e}" in error_messages
