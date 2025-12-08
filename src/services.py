# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from collections import ChainMap
from pathlib import PurePath
from typing import Optional

from ops.model import Container, ModelError, Unit
from ops.pebble import CheckStatus, Layer, LayerDict, ServiceInfo

from cli import CommandLine
from constants import (
    ADMIN_SERVICE_COMMAND,
    ADMIN_SERVICE_PORT,
    CA_CERT_DIR_PATH,
    PEBBLE_READY_CHECK_NAME,
    WORKLOAD_CONTAINER,
    WORKLOAD_SERVICE,
)
from env_vars import DEFAULT_CONTAINER_ENV, EnvVarConvertible
from exceptions import PebbleServiceError
from integrations import OpenFGAIntegrationData

logger = logging.getLogger(__name__)


PEBBLE_LAYER_DICT = {
    "summary": "Pebble Layer for Identity Platform Admin UI",
    "description": "Pebble Layer for Identity Platform Admin UI",
    "services": {
        WORKLOAD_SERVICE: {
            "override": "replace",
            "summary": "identity platform admin ui",
            "command": ADMIN_SERVICE_COMMAND,
            "startup": "enabled",
            "environment": DEFAULT_CONTAINER_ENV,
        }
    },
    "checks": {
        PEBBLE_READY_CHECK_NAME: {
            "override": "replace",
            "http": {"url": f"http://localhost:{ADMIN_SERVICE_PORT}/api/v0/status"},
        },
    },
}


class WorkloadService:
    """Workload service abstraction running in a Juju unit."""

    def __init__(self, unit: Unit) -> None:
        self._version: str = ""

        self._unit: Unit = unit
        self._container: Container = unit.get_container(WORKLOAD_CONTAINER)
        self._cli = CommandLine(self._container)

    @property
    def version(self) -> str:
        self._version = self._cli.get_admin_service_version() or ""
        return self._version

    @version.setter
    def version(self, version: str) -> None:
        if not version:
            return

        try:
            self._unit.set_workload_version(version)
        except Exception as e:
            logger.error("Failed to set workload version: %s", e)
            return
        else:
            self._version = version

    def get_service(self) -> Optional[ServiceInfo]:
        try:
            return self._container.get_service(WORKLOAD_SERVICE)
        except (ModelError, ConnectionError) as e:
            logger.error("Failed to get pebble service: %s", e)
        return None

    def is_running(self) -> bool:
        if not (service := self.get_service()):
            return False

        if not service.is_running():
            return False

        c = self._container.get_checks().get("ready")
        return c.status == CheckStatus.UP

    def is_failing(self) -> bool:
        """Checks whether the service has crashed."""
        if not self.get_service():
            return False

        if not (c := self._container.get_checks().get(PEBBLE_READY_CHECK_NAME)):
            return False

        return c.failures > 0

    def open_port(self) -> None:
        self._unit.open_port(protocol="tcp", port=ADMIN_SERVICE_PORT)

    def prepare_dir(self, path: str | PurePath) -> None:
        if self._container.isdir(path):
            return

        self._container.make_dir(path=path, make_parents=True)

    def push_ca_certs(self, ca_certs: str | PurePath) -> None:
        self._container.push(CA_CERT_DIR_PATH / "ca-certificates.crt", ca_certs, make_dirs=True)

    def create_openfga_model(self, openfga_data: OpenFGAIntegrationData) -> str:
        model_id = self._cli.create_openfga_model(
            openfga_data.url,
            openfga_data.api_token,
            openfga_data.store_id,
        )

        return model_id or ""


class PebbleService:
    """Pebble service abstraction running in a Juju unit."""

    def __init__(self, unit: Unit) -> None:
        self._unit = unit
        self._container = unit.get_container(WORKLOAD_SERVICE)
        self._layer_dict: LayerDict = PEBBLE_LAYER_DICT

    def plan(self, layer: Layer) -> None:
        self._container.add_layer(WORKLOAD_CONTAINER, layer, combine=True)

        try:
            self._container.replan()
        except Exception as e:
            raise PebbleServiceError(f"Pebble plan failed. Error: {e}")

    def stop(self) -> None:
        try:
            self._container.stop(WORKLOAD_SERVICE)
        except Exception as e:
            raise PebbleServiceError(f"Pebble failed to stop the workload service. Error: {e}")

    def render_pebble_layer(self, *env_var_sources: EnvVarConvertible) -> Layer:
        updated_env_vars = ChainMap(*(source.to_env_vars() for source in env_var_sources))  # type: ignore
        env_vars = {
            **DEFAULT_CONTAINER_ENV,
            **updated_env_vars,
        }
        self._layer_dict["services"][WORKLOAD_SERVICE]["environment"] = env_vars

        return Layer(self._layer_dict)
