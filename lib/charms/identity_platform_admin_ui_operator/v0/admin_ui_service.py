#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Description
"""

import logging
from typing import Dict

from ops.charm import CharmBase, RelationCreatedEvent
from ops.framework import EventBase, EventSource, Object, ObjectEvents

# The unique Charmhub library identifier, never change it
LIBID = "temporary"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1

INTERFACE_NAME = "admin_ui_service"
logger = logging.getLogger(__name__)

# Generic Classes for relation. Please use appropriate subclass for the relation.


class AdminUIServiceRelationReadyEvent(EventBase):
    """Event to notify the charm that the relation is ready."""


class AdminUIServiceProviderEvents(ObjectEvents):
    """Event descriptor for events raised by `AdminUIServiceProvider`."""

    ready = EventSource(AdminUIServiceRelationReadyEvent)


class GenericAdminUIServiceProvider(Object):
    """Generic Provider of the admin_ui_service interface"""

    on = AdminUIServiceProviderEvents()

    def __init__(self, charm: CharmBase, relation_name: str):
        super().__init__(charm, relation_name)

        self._charm = charm
        self._relation_name = relation_name

        events = self._charm.on[relation_name]
        self.framework.observe(
            events.relation_created, self._on_admin_ui_service_provider_ready
        )

    def _on_admin_ui_service_provider_ready(self, event: RelationCreatedEvent) -> None:
        self.on.ready.emit()

    def send_relation_data_for_admin_ui(self, relation_data: Dict) -> None:
        """Updates relation with data in relation_data parameter"""
        if not self._charm.unit.is_leader():
            return

        relations = self.model.relations[self._relation_name]
        for relation in relations:
            relation.data[self._charm.app].update(
                relation_data
            )


class AdminUIServiceRelationError(Exception):
    """Base class for relation exceptions."""

    pass


class AdminUIServiceRelationMissingError(AdminUIServiceRelationError):
    """Raised when the relation is missing."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class AdminUIServiceRelationDataMissingError(AdminUIServiceRelationError):
    """Raised when information is missing from relation data."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class GenericAdminUIServiceRequirer(Object):
    """Generic Requirer of the admin_ui_service interface"""

    def __init__(self, charm: CharmBase, relation_name: str) -> None:
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

    def get_relation_data(self) -> Dict:
        """Receive relation data."""
        relation = self.model.relations[self._relation_name]
        if len(relation) == 0:
            raise AdminUIServiceRelationMissingError(
                f"Missing {self._relation_name} relation"
            )

        return relation[0].data[relation[0].app]
