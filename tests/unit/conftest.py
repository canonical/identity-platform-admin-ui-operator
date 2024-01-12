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
