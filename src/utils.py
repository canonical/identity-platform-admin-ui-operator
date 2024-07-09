# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from ops.charm import CharmBase, EventBase
from ops.model import BlockedStatus, WaitingStatus

from constants import (
    CERTIFICATE_TRANSFER_INTEGRATION_NAME,
    HYDRA_ENDPOINTS_INTEGRATION_NAME,
    INGRESS_INTEGRATION_NAME,
    KRATOS_INFO_INTEGRATION_NAME,
    OPENFGA_INTEGRATION_NAME,
    PEER_INTEGRATION_NAME,
    WORKLOAD_CONTAINER,
)

logger = logging.getLogger(__name__)

CharmEventHandler = TypeVar("CharmEventHandler", bound=Callable[..., Any])
Condition = Callable[[CharmBase], bool]


def leader_unit(func: CharmEventHandler) -> CharmEventHandler:
    """A decorator, applied to any event hook handler, to validate juju unit leadership."""

    @wraps(func)
    def wrapper(charm: CharmBase, *args: Any, **kwargs: Any) -> Optional[Any]:
        if not charm.unit.is_leader():
            return None

        return func(charm, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


def integration_existence(integration_name: str) -> Condition:
    """A factory of integration existence condition."""

    def wrapped(charm: CharmBase) -> bool:
        return bool(charm.model.relations[integration_name])

    return wrapped


peer_integration_existence = integration_existence(PEER_INTEGRATION_NAME)
kratos_integration_existence = integration_existence(KRATOS_INFO_INTEGRATION_NAME)
hydra_integration_existence = integration_existence(HYDRA_ENDPOINTS_INTEGRATION_NAME)
openfga_integration_existence = integration_existence(OPENFGA_INTEGRATION_NAME)
ingress_integration_existence = integration_existence(INGRESS_INTEGRATION_NAME)


def container_connectivity(charm: CharmBase) -> bool:
    return charm.unit.get_container(WORKLOAD_CONTAINER).can_connect()


def certificate_existence(charm: CharmBase) -> bool:
    oauth_integration_exists = charm.oauth_integration.is_ready()
    cert_transfer_integration_exists = bool(
        charm.model.relations[CERTIFICATE_TRANSFER_INTEGRATION_NAME]
    )

    return False if (oauth_integration_exists and not cert_transfer_integration_exists) else True


def openfga_store_readiness(charm: CharmBase) -> bool:
    return charm.openfga_integration.is_store_ready()


def openfga_model_readiness(charm: CharmBase) -> bool:
    return bool(charm.peer_data[charm._workload_service.version])


CONDITION_STATUS_REGISTRY = (
    (container_connectivity, WaitingStatus("Container is not connected yet")),
    (peer_integration_existence, WaitingStatus(f"Missing integration {PEER_INTEGRATION_NAME}")),
    (
        kratos_integration_existence,
        BlockedStatus(f"Missing integration {KRATOS_INFO_INTEGRATION_NAME}"),
    ),
    (
        hydra_integration_existence,
        BlockedStatus(f"Missing integration {HYDRA_ENDPOINTS_INTEGRATION_NAME}"),
    ),
    (
        openfga_integration_existence,
        BlockedStatus(f"Missing integration {OPENFGA_INTEGRATION_NAME}"),
    ),
    (
        ingress_integration_existence,
        BlockedStatus(f"Missing integration {INGRESS_INTEGRATION_NAME}"),
    ),
    (
        certificate_existence,
        BlockedStatus("Missing certificate transfer integration with oauth provider"),
    ),
    (openfga_store_readiness, WaitingStatus("OpenFGA store is not ready yet")),
    (openfga_model_readiness, WaitingStatus("OpenFGA model is not ready yet")),
)


def do_nothing(event: EventBase) -> None:
    pass


def defer_event(event: EventBase) -> None:
    event.defer()


CONDITION_SIDE_EFFECT_REGISTRY = (
    (container_connectivity, defer_event),
    (peer_integration_existence, defer_event),
    (kratos_integration_existence, do_nothing),
    (hydra_integration_existence, do_nothing),
    (openfga_integration_existence, do_nothing),
    (ingress_integration_existence, do_nothing),
    (certificate_existence, do_nothing),
    (openfga_store_readiness, defer_event),
    (openfga_model_readiness, defer_event),
)
