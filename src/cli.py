# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import re
from typing import List, Optional

from ops.model import Container
from ops.pebble import Error, ExecError

VERSION_REGEX = re.compile(r"App Version:\s*(?P<version>\S+)\s*$")
MODEL_REGEX = re.compile(r"Created model:\s*(?P<model>\S+)")

logger = logging.getLogger(__name__)


class CommandLine:
    """A class to handle command line interactions with admin service."""

    def __init__(self, container: Container):
        self.container = container

    def get_admin_service_version(self) -> Optional[str]:
        cmd = ["identity-platform-admin-ui", "version"]

        try:
            stdout = self._run_cmd(cmd)
        except ExecError as err:
            logger.error("Exited with code: %d. Error: %s", err.exit_code, err.stderr)
            return None
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
        except ExecError as err:
            logger.error("Exited with code: %d. Error: %s", err.exit_code, err.stderr)
            return None
        except Error as err:
            logger.error("Failed to create the OpenFGA model: %s", err)
            return None

        matched = MODEL_REGEX.search(stdout)
        return matched.group("model") if matched else None

    def _run_cmd(
        self,
        cmd: List[str],
        timeout: float = 20,
    ) -> str:
        logger.debug(f"Running command: {cmd}")
        process = self.container.exec(cmd, timeout=timeout)
        stdout, _ = process.wait_output()
        return stdout
