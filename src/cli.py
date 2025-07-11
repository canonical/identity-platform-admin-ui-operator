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
from exceptions import MigrationError

VERSION_REGEX = re.compile(r"App Version:\s*(?P<version>\S+)\s*$")
MODEL_REGEX = re.compile(r"Created model:\s*(?P<model>\S+)")
IDENTITY_REGEX = re.compile(r"Identity created:\s*(?P<identity>\S+)")

logger = logging.getLogger(__name__)


@dataclass
class CmdExecConfig:
    service_context: Optional[str] = None
    environment: EnvVars = field(default_factory=dict)
    timeout: float = 20
    stdin: Optional[str | bytes | TextIO | BinaryIO] = None


class CommandLine:
    """A class to handle command line interactions with admin service."""

    def __init__(self, container: Container):
        self.container = container

    def get_admin_service_version(self) -> Optional[str]:
        cmd = ["identity-platform-admin-ui", "version"]

        try:
            stdout, _ = self._run_cmd(cmd)
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
            stdout, _ = self._run_cmd(cmd)
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
            stdout, _ = self._run_cmd(
                cmd,
                exec_config=CmdExecConfig(
                    service_context=WORKLOAD_SERVICE, stdin=json.dumps(identity)
                ),
            )
        except Error as err:
            logger.error("Failed to create the identity: %s", err)
            return None

        matched = IDENTITY_REGEX.search(stdout)
        return matched.group("identity") if matched else None

    def migrate_up(self, dsn: str, timeout: float = 120) -> None:
        cmd = [
            "identity-platform-admin-ui",
            "migrate",
            "--dsn",
            dsn,
            "up",
        ]

        try:
            self._run_cmd(
                cmd,
                exec_config=CmdExecConfig(service_context=WORKLOAD_SERVICE, timeout=timeout),
            )
        except Error as err:
            logger.error("Failed to migrate up the admin-ui service: %s", err)
            raise MigrationError from err

    def migrate_down(self, dsn: str, version: Optional[str] = None, timeout: float = 120) -> None:
        cmd = [
            "identity-platform-admin-ui",
            "migrate",
            "--dsn",
            dsn,
            "down",
        ]

        if version:
            cmd.extend([version])

        try:
            self._run_cmd(
                cmd,
                exec_config=CmdExecConfig(service_context=WORKLOAD_SERVICE, timeout=timeout),
            )
        except Error as err:
            logger.error("Failed to migrate down the admin-ui service: %s", err)
            raise MigrationError from err

    def migrate_status(self, dsn: str) -> Optional[str]:
        cmd = [
            "identity-platform-admin-ui",
            "migrate",
            "--dsn",
            dsn,
            "status",
        ]

        try:
            _, stderr = self._run_cmd(
                cmd,
                exec_config=CmdExecConfig(service_context=WORKLOAD_SERVICE),
            )
            return stderr
        except Error as err:
            logger.error("Failed to fetch migration status: %s", err)
            return None

    def _run_cmd(
        self,
        cmd: List[str],
        exec_config: CmdExecConfig = CmdExecConfig(),
    ) -> tuple[str, str]:
        logger.debug(f"Running command: {cmd}")

        process = self.container.exec(cmd, **asdict(exec_config))
        try:
            stdout, stderr = process.wait_output()
        except ExecError as err:
            logger.error("Exited with code: %d. Error: %s", err.exit_code, err.stderr)
            raise

        return stdout, stderr if stderr else ""
