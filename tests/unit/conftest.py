# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Generator
from unittest.mock import MagicMock

import pytest
from ops.testing import Harness
from pytest_mock import MockerFixture

from charm import IdentityPlatformAdminUIOperatorCharm


@pytest.fixture()
def harness() -> Generator[Harness, None, None]:
    harness = Harness(IdentityPlatformAdminUIOperatorCharm)
    harness.set_model_name("testing")
    harness.set_leader(True)
    harness.begin()
    yield harness
    harness.cleanup()


@pytest.fixture(autouse=True)
def mocked_get_version(harness: Harness):
    harness.handle_exec(
        "admin-ui", ["identity-platform-admin-ui", "--version"], result="App Version: 1.2.0"
    )


@pytest.fixture(autouse=True)
def mocked_log_proxy_consumer_setup_promtail(mocker: MockerFixture) -> MagicMock:
    mocked_setup_promtail = mocker.patch(
        "charms.loki_k8s.v0.loki_push_api.LogProxyConsumer._setup_promtail", return_value=None
    )
    return mocked_setup_promtail


@pytest.fixture()
def mocked_hydra_url(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentityPlatformAdminUIOperatorCharm._get_hydra_endpoint_info",
        return_value="http://hydra-url.com",
    )


@pytest.fixture()
def mocked_kratos_url(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentityPlatformAdminUIOperatorCharm._get_kratos_endpoint_info",
        return_value="http://kratos-url.com",
    )


@pytest.fixture()
def mocked_log_level(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentityPlatformAdminUIOperatorCharm._log_level", return_value="warning"
    )
