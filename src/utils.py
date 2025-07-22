# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from ops.charm import CharmBase

from constants import (
    CERTIFICATE_TRANSFER_INTEGRATION_NAME,
    DATABASE_INTEGRATION_NAME,
    HYDRA_ENDPOINTS_INTEGRATION_NAME,
    INGRESS_INTEGRATION_NAME,
    KRATOS_INFO_INTEGRATION_NAME,
    OAUTH_INTEGRATION_NAME,
    OPENFGA_INTEGRATION_NAME,
    OPENFGA_MODEL_ID,
    PEER_INTEGRATION_NAME,
    SMTP_INTEGRATION_NAME,
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


peer_integration_exists = integration_existence(PEER_INTEGRATION_NAME)
kratos_integration_exists = integration_existence(KRATOS_INFO_INTEGRATION_NAME)
hydra_integration_exists = integration_existence(HYDRA_ENDPOINTS_INTEGRATION_NAME)
openfga_integration_exists = integration_existence(OPENFGA_INTEGRATION_NAME)
ingress_integration_exists = integration_existence(INGRESS_INTEGRATION_NAME)
oauth_integration_exists = integration_existence(OAUTH_INTEGRATION_NAME)
cert_transfer_integration_exists = integration_existence(CERTIFICATE_TRANSFER_INTEGRATION_NAME)
smtp_integration_exists = integration_existence(SMTP_INTEGRATION_NAME)
database_integration_exists = integration_existence(DATABASE_INTEGRATION_NAME)


def container_connectivity(charm: CharmBase) -> bool:
    return charm.unit.get_container(WORKLOAD_CONTAINER).can_connect()


def oauth_is_ready(charm: CharmBase) -> bool:
    return charm.oauth_integration.is_ready()


def ca_certificate_exists(charm: CharmBase) -> bool:
    return (
        oauth_integration_exists(charm)
        and cert_transfer_integration_exists(charm)
        and charm._ca_bundle
    )


def openfga_store_readiness(charm: CharmBase) -> bool:
    return charm.openfga_integration.is_store_ready()


def openfga_model_readiness(charm: CharmBase) -> bool:
    version = charm._workload_service.version

    if not (openfga_model := charm.peer_data[version]):
        return False

    return bool(openfga_model.get(OPENFGA_MODEL_ID))


def migration_needed_on_non_leader(charm: CharmBase) -> bool:
    return charm.migration_needed and not charm.unit.is_leader()


def migration_needed_on_leader(charm: CharmBase) -> bool:
    return charm.migration_needed and charm.unit.is_leader()


# Condition failure causes early returns without doing anything
NOOP_CONDITIONS: tuple[Condition, ...] = (
    kratos_integration_exists,
    hydra_integration_exists,
    oauth_integration_exists,
    openfga_integration_exists,
    ingress_integration_exists,
    ca_certificate_exists,
    database_integration_exists,
)


# Condition failure causes early return with corresponding event deferred
EVENT_DEFER_CONDITIONS: tuple[Condition, ...] = (
    container_connectivity,
    peer_integration_exists,
    openfga_store_readiness,
    openfga_model_readiness,
)
