# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Generator
from unittest.mock import MagicMock, PropertyMock, create_autospec

import pytest
from ops import CollectStatusEvent, EventBase
from ops.model import Container, Unit
from ops.testing import Harness
from pytest_mock import MockerFixture

from charm import IdentityPlatformAdminUIOperatorCharm
from constants import (
    CERTIFICATE_TRANSFER_INTEGRATION_NAME,
    DEFAULT_CONTEXT_PATH,
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
def mocked_pebble_service(mocker: MockerFixture, harness: Harness) -> MagicMock:
    mocked = mocker.patch("charm.PebbleService", autospec=True)
    harness.charm._pebble_service = mocked
    return mocked


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
    return mocker.patch("charm.IdentityPlatformAdminUIOperatorCharm._holistic_handler")


@pytest.fixture
def mocked_ingress_data(mocker: MockerFixture) -> IngressData:
    mocked = mocker.patch(
        "charm.IngressData.load",
        return_value=IngressData(is_ready=True, url=DEFAULT_CONTEXT_PATH),
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
def mocked_event() -> MagicMock:
    return create_autospec(EventBase)


@pytest.fixture
def mocked_collect_status_event() -> MagicMock:
    return create_autospec(CollectStatusEvent)


@pytest.fixture
def peer_integration(harness: Harness) -> int:
    return harness.add_relation(PEER_INTEGRATION_NAME, "identity-platform-admin-ui")


@pytest.fixture
def ingress_integration(harness: Harness) -> int:
    return harness.add_relation(
        INGRESS_INTEGRATION_NAME,
        "ingress",
    )


@pytest.fixture
def certificate_transfer_integration(harness: Harness) -> int:
    return harness.add_relation(
        CERTIFICATE_TRANSFER_INTEGRATION_NAME,
        "self-signed-certificate",
    )


@pytest.fixture
def all_satisfied_conditions(mocker: MockerFixture) -> None:
    mocker.patch("charm.container_connectivity", return_value=True)
    mocker.patch("charm.peer_integration_exists", return_value=True)
    mocker.patch("charm.kratos_integration_exists", return_value=True)
    mocker.patch("charm.hydra_integration_exists", return_value=True)
    mocker.patch("charm.openfga_integration_exists", return_value=True)
    mocker.patch("charm.ingress_integration_exists", return_value=True)
    mocker.patch("charm.ca_certificate_exists", return_value=True)
    mocker.patch("charm.openfga_store_readiness", return_value=True)
    mocker.patch("charm.openfga_model_readiness", return_value=True)
