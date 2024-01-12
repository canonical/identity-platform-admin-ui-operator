# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

"""Test functions for unit testing Identity Platform Admin UI Operator."""
import json

from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.testing import Harness

CONTAINER_NAME = "admin-ui"

# Relation Mocks


def setup_loki_relation(harness: Harness) -> int:
    relation_id = harness.add_relation("logging", "loki-k8s")
    harness.add_relation_unit(relation_id, "loki-k8s/0")
    databag = {
        "promtail_binary_zip_url": json.dumps(
            {
                "amd64": {
                    "filename": "promtail-static-amd64",
                    "zipsha": "543e333b0184e14015a42c3c9e9e66d2464aaa66eca48b29e185a6a18f67ab6d",
                    "binsha": "17e2e271e65f793a9fbe81eab887b941e9d680abe82d5a0602888c50f5e0cac9",
                    "url": "https://github.com/canonical/loki-k8s-operator/releases/download/promtail-v2.5.0/promtail-static-amd64.gz",
                }
            }
        ),
    }
    unit_databag = {
        "endpoint": json.dumps(
            {
                "url": "http://loki-k8s-0.loki-k8s-endpoints.cos.svc.cluster.local:3100/loki/api/v1/push"
            }
        )
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


def setup_kratos_relation(harness: Harness) -> int:
    relation_id = harness.add_relation("kratos-admin-endpoint", "kratos")
    harness.add_relation_unit(relation_id, "kratos/0")

    databag = {
        "admin_endpoint": f"http://kratos-admin-url:80/{harness.model.name}-kratos",
        "public_endpoint": f"http://kratos-public-url:80/{harness.model.name}-kratos",
        "model": harness.model.name,
        "idp_configmap": "test-idp-cm",
        "schemas_configmap": "test-schemas-cm",
    }
    harness.update_relation_data(
        relation_id,
        "kratos",
        databag,
    )
    return relation_id


def setup_hydra_relation(harness: Harness) -> int:
    relation_id = harness.add_relation("hydra-admin-endpoint", "hydra")
    harness.add_relation_unit(relation_id, "hydra/0")

    databag = {"admin_endpoint": f"http://hydra-admin-url:80/{harness.model.name}-hydra"}
    harness.update_relation_data(
        relation_id,
        "hydra",
        databag,
    )
    return relation_id


def setup_oathkeeper_relation(harness: Harness) -> int:
    relation_id = harness.add_relation("oathkeeper-admin-endpoint", "oathkeeper")
    harness.add_relation_unit(relation_id, "oathkeeper/0")

    databag = {
        "public_endpoint": f"http://oathkeeper-url:80/{harness.model.name}-oathkeeper",
        "rules_configmap": "test-rules-cm",
        "rules_file": "test-rules-file",
        "model": harness.model.name,
    }
    harness.update_relation_data(
        relation_id,
        "oathkeeper",
        databag,
    )
    return relation_id


# Unit tests for Charm events


def test_on_config_changed(harness: Harness) -> None:
    harness.set_leader(True)
    harness.set_can_connect(CONTAINER_NAME, True)
    harness.charm.on.admin_ui_pebble_ready.emit(CONTAINER_NAME)

    harness.update_config(
        {
            "log_level": "debug",
        }
    )
    harness.charm.on.config_changed.emit()

    expected_layer = {
        "summary": "Pebble Layer for Identity Platform Admin UI",
        "description": "Pebble Layer for Identity Platform Admin UI",
        "services": {
            CONTAINER_NAME: {
                "override": "replace",
                "summary": "identity platform admin ui",
                "command": "/usr/bin/identity-platform-admin-ui",
                "startup": "enabled",
                "environment": {
                    "PORT": "8080",
                    "TRACING_ENABLED": False,
                    "LOG_LEVEL": "debug",
                    "LOG_FILE": "/var/log/admin_ui.log",
                    "DEBUG": True,
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


def test_not_leader(harness: Harness) -> None:
    """Test with unit not being leader."""
    harness.set_leader(False)

    harness.charm.on.admin_ui_pebble_ready.emit(CONTAINER_NAME)

    assert (
        "status_set",
        "waiting",
        "Waiting to connect to admin-ui container",
        {"is_app": False},
    ) in harness._get_backend_calls()


def test_install_can_connect(harness: Harness) -> None:
    """Test installation with connection."""
    harness.set_leader(True)
    harness.set_can_connect(CONTAINER_NAME, True)
    harness.charm.on.admin_ui_pebble_ready.emit(CONTAINER_NAME)

    setup_kratos_relation(harness)
    setup_hydra_relation(harness)
    setup_oathkeeper_relation(harness)

    assert harness.charm.unit.status == ActiveStatus()
    assert harness.get_workload_version() == "1.2.0"


def test_install_can_not_connect(harness: Harness) -> None:
    """Test installation with connection."""
    harness.set_leader(True)
    harness.set_can_connect(CONTAINER_NAME, False)
    harness.charm.on.admin_ui_pebble_ready.emit(CONTAINER_NAME)

    assert harness.charm.unit.status == WaitingStatus("Waiting to connect to admin-ui container")


# Unit tests for relation events


def test_layer_updated_with_tracing_endpoint_info(harness: Harness) -> None:
    """Test Pebble Layer when relation data is in place."""
    harness.set_leader(True)
    harness.set_can_connect(CONTAINER_NAME, True)
    harness.charm.on.admin_ui_pebble_ready.emit(CONTAINER_NAME)
    setup_tempo_relation(harness)

    pebble_env = harness.charm._admin_ui_pebble_layer.to_dict()["services"][CONTAINER_NAME][
        "environment"
    ]

    assert (
        pebble_env["OTEL_HTTP_ENDPOINT"]
        == "tempo-k8s-0.tempo-k8s-endpoints.namespace.svc.cluster.local:4318"
    )
    assert (
        pebble_env["OTEL_GRPC_ENDPOINT"]
        == "tempo-k8s-0.tempo-k8s-endpoints.namespace.svc.cluster.local:4317"
    )
    assert pebble_env["TRACING_ENABLED"]


def test_on_pebble_ready_with_loki(harness: Harness) -> None:
    harness.set_leader(True)
    harness.set_can_connect(CONTAINER_NAME, True)
    container = harness.model.unit.get_container(CONTAINER_NAME)
    harness.charm.on.admin_ui_pebble_ready.emit(container)
    setup_kratos_relation(harness)
    setup_hydra_relation(harness)
    setup_oathkeeper_relation(harness)
    setup_loki_relation(harness)

    assert harness.model.unit.status == ActiveStatus()


def test_iam_relations_missing(harness: Harness) -> None:
    harness.set_leader(True)
    harness.set_can_connect(CONTAINER_NAME, True)
    container = harness.model.unit.get_container(CONTAINER_NAME)
    harness.charm.on.admin_ui_pebble_ready.emit(container)

    assert harness.charm.unit.status == BlockedStatus("Missing required relation with Kratos")


def test_one_iam_relation_missing(harness: Harness) -> None:
    harness.set_leader(True)
    harness.set_can_connect(CONTAINER_NAME, True)
    container = harness.model.unit.get_container(CONTAINER_NAME)
    harness.charm.on.admin_ui_pebble_ready.emit(container)

    setup_kratos_relation(harness)
    setup_hydra_relation(harness)

    assert harness.charm.unit.status == BlockedStatus("Missing required relation with Oathkeeper")


def layer_updated_with_iam_relations(harness: Harness) -> None:
    harness.set_leader(True)
    harness.set_can_connect(CONTAINER_NAME, True)
    container = harness.model.unit.get_container(CONTAINER_NAME)
    harness.charm.on.admin_ui_pebble_ready.emit(container)

    setup_kratos_relation(harness)
    setup_hydra_relation(harness)
    setup_oathkeeper_relation(harness)

    assert harness.model.unit.status == ActiveStatus()

    expected_layer = {
        "summary": "Pebble Layer for Identity Platform Admin UI",
        "description": "Pebble Layer for Identity Platform Admin UI",
        "services": {
            CONTAINER_NAME: {
                "override": "replace",
                "summary": "identity platform admin ui",
                "command": "/usr/bin/identity-platform-admin-ui",
                "startup": "enabled",
                "environment": {
                    "KRATOS_PUBLIC_URL": "http://kratos-admin-url:80/testing-kratos",
                    "KRATOS_ADMIN_URL": "http://kratos-public-url:80/testing-kratos",
                    "HYDRA_ADMIN_URL": "http://hydra-admin-url:80/testing-hydra",
                    "OATHKEEPER_PUBLIC_URL": "http://oathkeeper-url:80/testing-oathkeeper",
                    "IDP_CONFIGMAP_NAME": "test-idp-cm",
                    "IDP_CONFIGMAP_NAMESPACE": "testing",
                    "SCHEMAS_CONFIGMAP_NAME": "test-schemas-cm",
                    "SCHEMAS_CONFIGMAP_NAMESPACE": "testing",
                    "RULES_CONFIGMAP_NAME": "test-rules-cm",
                    "RULES_CONFIGMAP_FILE_NAME": "test-rules-file",
                    "RULES_CONFIGMAP_NAMESPACE": "testing",
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
