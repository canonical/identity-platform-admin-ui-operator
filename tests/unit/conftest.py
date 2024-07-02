# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Generator
from unittest.mock import MagicMock, PropertyMock, create_autospec

import pytest
from ops.model import Container, Unit
from ops.testing import Harness
from pytest_mock import MockerFixture

from charm import IdentityPlatformAdminUIOperatorCharm
from constants import (
    DEFAULT_BASE_URL,
    INGRESS_INTEGRATION_NAME,
    PEER_INTEGRATION_NAME,
    WORKLOAD_CONTAINER,
)
from integrations import IngressData


@pytest.fixture()
def harness() -> Generator[Harness, None, None]:
    harness = Harness(IdentityPlatformAdminUIOperatorCharm)
    harness.set_model_name("testing")
    harness.set_leader(True)
    harness.set_can_connect(WORKLOAD_CONTAINER, True)
    harness.begin()
    yield harness
    harness.cleanup()


@pytest.fixture
def mocked_workload_service(mocker: MockerFixture, harness: Harness) -> MagicMock:
    mocked = mocker.patch("charm.WorkloadService", autospec=True)
    harness.charm._workload_service = mocked
    return mocked


@pytest.fixture
def mocked_workload_service_version(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.WorkloadService.version", new_callable=PropertyMock, return_value="1.10.0"
    )


@pytest.fixture
def mocked_oauth_integration(mocker: MockerFixture, harness: Harness) -> MagicMock:
    mocked = mocker.patch("charm.OAuthIntegration", autospec=True)
    harness.charm.oauth_integration = mocked
    return mocked


@pytest.fixture
def mocked_openfga_store_ready(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.OpenFGAIntegration.is_store_ready", return_value=True)


@pytest.fixture
def mocked_charm_holistic_handler(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.IdentityPlatformAdminUIOperatorCharm._handle_status_update_config")


@pytest.fixture
def mocked_ingress_data(mocker: MockerFixture) -> IngressData:
    mocked = mocker.patch(
        "charm.IngressIntegration.ingress_data",
        new_callable=PropertyMock,
        return_value=IngressData(is_ready=True, url=DEFAULT_BASE_URL),
    )
    return mocked.return_value


@pytest.fixture
def mocked_container() -> MagicMock:
    return create_autospec(Container)


@pytest.fixture
def mocked_unit(mocked_container: MagicMock) -> MagicMock:
    mocked = create_autospec(Unit)
    mocked.get_container.return_value = mocked_container
    return mocked


@pytest.fixture
def peer_integration(harness: Harness) -> int:
    return harness.add_relation(PEER_INTEGRATION_NAME, "identity-platform-admin-ui")


@pytest.fixture
def ingress_integration(harness: Harness) -> int:
    return harness.add_relation(
        INGRESS_INTEGRATION_NAME,
        "ingress",
    )
