# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""A helper class for interacting with the Admin UI CLI."""

import logging
import re
from typing import List, Optional, Tuple, Union

from charms.openfga_k8s.v1.openfga import OpenfgaProviderAppData
from ops.model import Container

logger = logging.getLogger(__name__)


class CommandOutputParseExceptionError(Exception):
    """Raised when the command output parsing fails."""


class AdminUICLI:
    """Helper object for running Admin UI CLI commands."""

    def __init__(self, container: Container):
        self.container = container

    def get_version(self) -> Optional[str]:
        """Get the version of admin ui binary."""
        cmd = ["identity-platform-admin-ui", "version"]

        stdout, _ = self._run_cmd(cmd)

        out_re = r"App Version:\s*(.+)\s*$"
        versions = re.search(out_re, stdout)
        if versions:
            return versions[1]

    def create_openfga_model(self, openfga_info: OpenfgaProviderAppData) -> Optional[str]:
        """Create an openfga model."""
        cmd = [
            "identity-platform-admin-ui",
            "create-fga-model",
            "--fga-api-url",
            openfga_info.http_api_url,
            "--fga-api-token",
            openfga_info.token,
            "--fga-store-id",
            openfga_info.store_id,
        ]

        stdout, _ = self._run_cmd(cmd)

        out_re = r"Created model:\s*(.+)"
        model = re.search(out_re, stdout)
        if model:
            return model[1]
        else:
            raise CommandOutputParseExceptionError("Failed to parse the command output")

    def _run_cmd(
        self,
        cmd: List[str],
        timeout: float = 20,
    ) -> Tuple[Union[str, bytes], Union[str, bytes]]:
        logger.debug(f"Running cmd: {cmd}")
        process = self.container.exec(cmd, timeout=timeout)
        stdout, stderr = process.wait_output()
        return stdout, stderr
