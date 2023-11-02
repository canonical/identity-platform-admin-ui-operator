# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit test configuration."""
from unittest.mock import MagicMock

import ops.testing
import pytest
from ops.testing import Harness
from pytest_mock import MockerFixture

from charm import IdentityPlatformAdminUiOperatorCharm


@pytest.fixture()
def harness(mocked_kubernetes_service_patcher: MagicMock) -> ops.testing.Harness:
    """Initialize harness with Charm."""
    harness = ops.testing.Harness(IdentityPlatformAdminUiOperatorCharm)
    harness.set_model_name("testing")
    harness.begin()
    return harness


@pytest.fixture(autouse=True)
def mock_get_version(harness: Harness):
    harness.handle_exec(
        "admin-ui", ["identity-platform-admin-ui", "--version"], result="App Version: 1.2.0"
    )


@pytest.fixture()
def mocked_kubernetes_service_patcher(mocker: MockerFixture) -> MagicMock:
    mocked_service_patcher = mocker.patch("charm.KubernetesServicePatch")
    mocked_service_patcher.return_value = lambda x, y: None
    return mocked_service_patcher


@pytest.fixture(autouse=True)
def mocked_log_proxy_consumer_setup_promtail(mocker: MockerFixture) -> MagicMock:
    mocked_setup_promtail = mocker.patch(
        "charms.loki_k8s.v0.loki_push_api.LogProxyConsumer._setup_promtail", return_value=None
    )
    return mocked_setup_promtail


"""Mocks for config properties. Will use these for unit tests when the relations are developed."""


@pytest.fixture()
def mocked_kratos_public_url(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentityPlatformAdminUiOperatorCharm._kratos_public_url",
        return_value="http://kratos-public-mock",
    )


@pytest.fixture()
def mocked_kratos_admin_url(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentityPlatformAdminUiOperatorCharm._kratos_admin_url",
        return_value="http://kratos-admin-mock",
    )


@pytest.fixture()
def mocked_hydra_admin_url(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentityPlatformAdminUiOperatorCharm._hydra_admin_url",
        return_value="http://hydra-admin-mock",
    )


@pytest.fixture()
def mocked_idp_configmap_name(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentityPlatformAdminUiOperatorCharm._idp_configmap_name", return_value="mock-idp"
    )


@pytest.fixture()
def mocked_idp_configmap_namespace(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentityPlatformAdminUiOperatorCharm._idp_configmap_namespace",
        return_value="mock-default",
    )


@pytest.fixture()
def mocked_schemas_configmap_name(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentityPlatformAdminUiOperatorCharm._schemas_configmap_name",
        return_value="mock-schemas",
    )


@pytest.fixture()
def mocked_schemas_configmap_namespace(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentityPlatformAdminUiOperatorCharm._schemas_configmap_namespace",
        return_value="mock-default",
    )


@pytest.fixture()
def mocked_port(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.IdentityPlatformAdminUiOperatorCharm._port", return_value="80")


@pytest.fixture()
def mocked_log_level(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentityPlatformAdminUiOperatorCharm._log_level", return_value="warning"
    )
