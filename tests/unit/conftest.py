# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Dict, Generator
from unittest.mock import MagicMock

import pytest
from charms.openfga_k8s.v1.openfga import OpenfgaProviderAppData
from ops.testing import Harness
from pytest_mock import MockerFixture

from charm import IdentityPlatformAdminUIOperatorCharm
from constants import OPENFGA_STORE_NAME


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
        "admin-ui", ["identity-platform-admin-ui", "version"], result="App Version: 1.2.0"
    )


@pytest.fixture()
def mocked_version(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.IdentityPlatformAdminUIOperatorCharm._set_version")


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
def mocked_log_level(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentityPlatformAdminUIOperatorCharm._log_level", return_value="warning"
    )


@pytest.fixture()
def mocked_handle_status_update_config(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentityPlatformAdminUIOperatorCharm._handle_status_update_config",
    )


@pytest.fixture()
def openfga_requirer_databag() -> Dict:
    return {"store_name": OPENFGA_STORE_NAME}


@pytest.fixture()
def mocked_openfga_store_info(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charms.openfga_k8s.v1.openfga.OpenFGARequires.get_store_info",
        return_value=OpenfgaProviderAppData(
            store_id="store_id",
            token="token",
            token_secret_id="token_secret_id",
            grpc_api_url="http://127.0.0.1:8081",
            http_api_url="http://127.0.0.1:8080",
        ),
    )


@pytest.fixture()
def mocked_openfga_model_id(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentityPlatformAdminUIOperatorCharm._openfga_model_id",
        return_value="01HQJMD174NPN2A4JFRFZ1NNW1",
    )


@pytest.fixture()
def mocked_create_model(mocker: MockerFixture) -> Generator:
    mock = mocker.patch("charm.AdminUICLI.create_openfga_model")
    mock.return_value = "01HQJMD174NPN2A4JFRFZ1NNW1"
    yield mock
