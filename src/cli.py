# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import BinaryIO, List, Optional, TextIO

from ops.model import Container
from ops.pebble import Error, ExecError

from constants import WORKLOAD_SERVICE
from env_vars import EnvVars

VERSION_REGEX = re.compile(r"App Version:\s*(?P<version>\S+)\s*$")
MODEL_REGEX = re.compile(r"Created model:\s*(?P<model>\S+)")
IDENTITY_REGEX = re.compile(r"Identity created:\s*(?P<identity>\S+)")

logger = logging.getLogger(__name__)


@dataclass
class CmdExecConfig:
    environment: EnvVars = field(default_factory=dict)
    timeout: int = 20
    stdin: Optional[str | bytes | TextIO | BinaryIO] = None


class CommandLine:
    """A class to handle command line interactions with admin service."""

    def __init__(self, container: Container):
        self.container = container

    def get_admin_service_version(self) -> Optional[str]:
        cmd = ["identity-platform-admin-ui", "version"]

        try:
            stdout = self._run_cmd(cmd)
        except Error as err:
            logger.error("Failed to fetch the Admin Service version: %s", err)
            return None

        matched = VERSION_REGEX.search(stdout)
        return matched.group("version") if matched else None

    def create_openfga_model(
        self,
        url: str,
        api_token: str,
        store_id: str,
    ) -> Optional[str]:
        cmd = [
            "identity-platform-admin-ui",
            "create-fga-model",
            "--fga-api-url",
            url,
            "--fga-api-token",
            api_token,
            "--fga-store-id",
            store_id,
        ]

        try:
            stdout = self._run_cmd(cmd)
        except Error as err:
            logger.error("Failed to create the OpenFGA model: %s", err)
            return None

        matched = MODEL_REGEX.search(stdout)
        return matched.group("model") if matched else None

    def create_identity(
        self, traits: dict, *, schema_id: str = "default", password: Optional[str] = None
    ) -> Optional[str]:
        identity = {"traits": traits, "schema_id": schema_id}
        if password:
            identity["credentials"] = {"password": {"config": {"password": password}}}

        cmd = [
            "identity-platform-admin-ui",
            "create-identity",
        ]

        try:
            stdout = self._run_cmd(cmd, exec_config=CmdExecConfig(stdin=json.dumps(identity)))
        except Error as err:
            logger.error("Failed to create the identity: %s", err)
            return None

        matched = IDENTITY_REGEX.search(stdout)
        return matched.group("identity") if matched else None

    def _run_cmd(
        self,
        cmd: List[str],
        exec_config: CmdExecConfig = CmdExecConfig(),
    ) -> str:
        logger.debug(f"Running command: {cmd}")

        pebble_plan = self.container.pebble.get_plan()
        workload_service_environment = pebble_plan.services[WORKLOAD_SERVICE].environment
        exec_config.environment = {**workload_service_environment, **exec_config.environment}

        process = self.container.exec(cmd, **asdict(exec_config))
        try:
            stdout, _ = process.wait_output()
        except ExecError as err:
            logger.error("Exited with code: %d. Error: %s", err.exit_code, err.stderr)
            raise

        return stdout
