# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from ops.charm import CharmBase, EventBase
from ops.model import BlockedStatus, WaitingStatus

logger = logging.getLogger(__name__)

CharmEventHandler = TypeVar("CharmEventHandler", bound=Callable[..., Any])
ConditionEvaluation = tuple[bool, str]
Condition = Callable[[CharmBase], ConditionEvaluation]


def container_not_connected(charm: CharmBase) -> ConditionEvaluation:
    """Condition to validate workload container connectivity."""
    not_connected = not charm._container.can_connect()
    return not_connected, ("Container is not connected yet" if not_connected else "")


def integration_not_exists(integration_name: str) -> Condition:
    """A factory of conditions of integration existence validation."""

    def wrapped(charm: CharmBase) -> ConditionEvaluation:
        not_exists = not charm.model.relations[integration_name]
        return not_exists, (f"Missing integration {integration_name}" if not_exists else "")

    return wrapped


def block_when(*conditions: Condition) -> Callable[[CharmEventHandler], CharmEventHandler]:
    """A factory of decorators that block juju unit when a certain condition validation fails."""

    def decorator(func: CharmEventHandler) -> CharmEventHandler:
        """A decorator, applied to any event hook handler, to block juju unit."""

        @wraps(func)
        def wrapper(charm: CharmBase, *args: EventBase, **kwargs: Any) -> Optional[Any]:
            event, *_ = args
            logger.debug(f"Handling event: {event}.")

            for condition in conditions:
                not_met, msg = condition(charm)
                if not_met:
                    charm.unit.status = BlockedStatus(msg)
                    return None

            return func(charm, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def wait_when(*conditions: Condition) -> Callable[[CharmEventHandler], CharmEventHandler]:
    """A factory of decorators that put juju unit in wait status when a certain condition validation fails."""

    def decorator(func: CharmEventHandler) -> CharmEventHandler:
        """A decorator, applied to any event hook handler, to put juju unit in wait status."""

        @wraps(func)
        def wrapper(charm: CharmBase, *args: EventBase, **kwargs: Any) -> Optional[Any]:
            event, *_ = args
            logger.debug(f"Handling event: {event}.")

            for condition in conditions:
                not_met, msg = condition(charm)
                if not_met:
                    event.defer()
                    charm.unit.status = WaitingStatus(msg)
                    return None

            return func(charm, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def leader_unit(func: CharmEventHandler) -> CharmEventHandler:
    """A decorator, applied to any event hook handler, to validate juju unit leadership."""

    @wraps(func)
    def wrapper(charm: CharmBase, *args: Any, **kwargs: Any) -> Optional[Any]:
        if not charm.unit.is_leader():
            return None

        return func(charm, *args, **kwargs)

    return wrapper  # type: ignore[return-value]
