#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Interface library for sharing oathkeeper info.

This library provides a Python API for both requesting and providing oathkeeper deployment info,
such as endpoints, namespace and ConfigMap details.
## Getting Started
To get started using the library, you need to fetch the library using `charmcraft`.
```shell
cd some-charm
charmcraft fetch-lib charms.oathkeeper.v0.oathkeeper_info
```
To use the library from the requirer side:
In the `metadata.yaml` of the charm, add the following:
```yaml
requires:
  oathkeeper-info:
    interface: oathkeeper_info
    limit: 1
```
Then, to initialise the library:
```python
from charms.oathkeeper.v0.oathkeeper_info import OathkeeperInfoRequirer
Class SomeCharm(CharmBase):
    def __init__(self, *args):
        self.oathkeeper_info_relation = OathkeeperInfoRequirer(self)
        self.framework.observe(self.on.some_event_emitted, self.some_event_function)
    def some_event_function():
        # fetch the relation info
        if self.oathkeeper_info_relation.is_ready():
            oathkeeper_data = self.oathkeeper_info_relation.get_oathkeeper_info()
```
"""

import logging
from typing import Dict, Optional

from ops.charm import CharmBase, RelationChangedEvent
from ops.framework import EventBase, EventSource, Object, ObjectEvents

# The unique Charmhub library identifier, never change it
LIBID = "c801a227f45b46099d7f87cff2dc6e39"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1

RELATION_NAME = "oathkeeper-info"
INTERFACE_NAME = "oathkeeper_info"
logger = logging.getLogger(__name__)


class OathkeeperInfoRelationChangedEvent(EventBase):
    """Event to notify the charm that the relation data has changed."""


class OathkeeperInfoProviderEvents(ObjectEvents):
    """Event descriptor for events raised by `OathkeeperInfoProvider`."""

    data_changed = EventSource(OathkeeperInfoRelationChangedEvent)


class OathkeeperInfoProvider(Object):
    """Provider side of the oathkeeper-info relation."""

    on = OathkeeperInfoProviderEvents()

    def __init__(self, charm: CharmBase, relation_name: str = RELATION_NAME):
        super().__init__(charm, relation_name)

        self._charm = charm
        self._relation_name = relation_name

        events = self._charm.on[relation_name]
        self.framework.observe(events.relation_changed, self._on_info_provider_relation_changed)

    def _on_info_provider_relation_changed(self, event: RelationChangedEvent) -> None:
        self.on.data_changed.emit()

    def send_info_relation_data(
        self,
        public_endpoint: str,
        rules_configmap_name: str,
        configmaps_namespace: str,
    ) -> None:
        """Updates relation with endpoints and configmaps info."""
        if not self._charm.unit.is_leader():
            return

        relations = self.model.relations[self._relation_name]
        info_databag = {
            "public_endpoint": public_endpoint,
            "rules_configmap_name": rules_configmap_name,
            "configmaps_namespace": configmaps_namespace,
        }

        for relation in relations:
            relation.data[self._charm.app].update(info_databag)

    def get_requirer_info(self) -> Optional[str]:
        """Get the requirer info."""
        info = self.model.relations[self._relation_name]
        if len(info) == 0:
            return None

        if not (app := info[0].app):
            return None

        data = info[0].data[app]

        if not data:
            logger.info("No relation data available.")
            return None

        return data.get("access_rules_file")


class OathkeeperInfoRelationError(Exception):
    """Base class for the relation exceptions."""

    pass


class OathkeeperInfoRelationMissingError(OathkeeperInfoRelationError):
    """Raised when the relation is missing."""

    def __init__(self) -> None:
        self.message = "Missing oathkeeper-info relation with oathkeeper"
        super().__init__(self.message)


class OathkeeperInfoRelationDataMissingError(OathkeeperInfoRelationError):
    """Raised when information is missing from the relation."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class OathkeeperInfoRequirer(Object):
    """Requirer side of the oathkeeper-info relation."""

    def __init__(self, charm: CharmBase, relation_name: str = RELATION_NAME):
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

    def update_requirer_info_relation_data(
        self,
        access_rules_file: str,
    ) -> None:
        """Updates relation with access rules info."""
        if not self._charm.unit.is_leader():
            return

        relations = self.model.relations[self._relation_name]
        info_databag = {
            "access_rules_file": access_rules_file,
        }

        for relation in relations:
            relation.data[self._charm.app].update(info_databag)

    def is_ready(self) -> bool:
        """Checks whether the relation data is ready.

        Returns True when Oathkeeper shared the config; False otherwise.
        """
        relation = self.model.get_relation(self._relation_name)
        if not relation or not relation.app or not relation.data[relation.app]:
            return False
        return True

    def get_oathkeeper_info(self) -> Optional[Dict]:
        """Get the oathkeeper info."""
        info = self.model.relations[self._relation_name]
        if len(info) == 0:
            raise OathkeeperInfoRelationMissingError()

        if not (app := info[0].app):
            raise OathkeeperInfoRelationMissingError()

        data = info[0].data[app]

        if not data:
            logger.info("No relation data available.")
            raise OathkeeperInfoRelationDataMissingError("Missing relation data")

        return data
