# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more about testing at: https://juju.is/docs/sdk/testing

from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest
from ops.pebble import Error, ExecError

from cli import CmdExecConfig, CommandLine


class TestCommandLine:
    @pytest.fixture
    def command_line(self, mocked_container: MagicMock) -> CommandLine:
        return CommandLine(mocked_container)

    def test_get_admin_service_version(self, command_line: CommandLine) -> None:
        expected = "1.0.0"
        with patch.object(command_line, "_run_cmd", return_value=f"App Version: {expected}"):
            actual = command_line.get_admin_service_version()
            assert actual == expected

    @pytest.mark.parametrize(
        "error",
        [ExecError(["cmd"], 1, "stdout", "stderr"), Error("error")],
    )
    def test_get_admin_service_version_failed(
        self, command_line: CommandLine, error: Error
    ) -> None:
        with patch.object(command_line, "_run_cmd", side_effect=error):
            actual = command_line.get_admin_service_version()

        assert actual is None

    def test_create_openfga_model(self, command_line: CommandLine) -> None:
        expected = "model_id"
        with patch.object(command_line, "_run_cmd", return_value=f"Created model: {expected}"):
            actual = command_line.create_openfga_model("url", "api_token", "store_id")

        assert actual == expected

    @pytest.mark.parametrize(
        "error",
        [ExecError(["cmd"], 1, "stdout", "stderr"), Error("error")],
    )
    def test_create_openfga_model_failed(self, command_line: CommandLine, error: Error) -> None:
        with patch.object(command_line, "_run_cmd", side_effect=error):
            actual = command_line.create_openfga_model("url", "api_token", "store_id")

        assert actual is None

    def test_create_identity(self, command_line: CommandLine) -> None:
        expected = "identity_id"
        with patch.object(command_line, "_run_cmd", return_value=f"Identity created: {expected}"):
            actual = command_line.create_identity(
                traits={"email": "test@canonical.com"},
                schema_id="schema_id",
                password="password",
            )

        assert actual == expected

    @pytest.mark.parametrize(
        "error",
        [ExecError(["cmd"], 1, "stdout", "stderr"), Error("error")],
    )
    def test_create_identity_failed(self, command_line: CommandLine, error: Error) -> None:
        with patch.object(command_line, "_run_cmd", side_effect=error):
            actual = command_line.create_identity(
                traits={"email": "test@canonical.com"},
                schema_id="schema_id",
                password="password",
            )

        assert actual is None

    def test_run_cmd(self, mocked_container: MagicMock, command_line: CommandLine) -> None:
        cmd, options, expected = (
            ["cmd"],
            CmdExecConfig(environment={"ENV": "VAR"}, timeout=60, stdin="stdin"),
            "stdout",
        )

        mocked_process = MagicMock(wait_output=MagicMock(return_value=(expected, "")))
        mocked_container.exec.return_value = mocked_process

        actual = command_line._run_cmd(cmd, exec_config=options)

        assert actual == expected
        mocked_container.exec.assert_called_once_with(cmd, **asdict(options))
