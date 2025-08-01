# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more about testing at: https://juju.is/docs/sdk/testing

from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest
from ops.pebble import Error, ExecError

from cli import CmdExecConfig, CommandLine
from exceptions import MigrationError


class TestCommandLine:
    @pytest.fixture
    def command_line(self, mocked_container: MagicMock) -> CommandLine:
        return CommandLine(mocked_container)

    def test_get_admin_service_version(self, command_line: CommandLine) -> None:
        expected = "1.0.0"
        with patch.object(command_line, "_run_cmd", return_value=(f"App Version: {expected}", "")):
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
        with patch.object(
            command_line, "_run_cmd", return_value=(f"Created model: {expected}", "")
        ):
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
        with patch.object(
            command_line, "_run_cmd", return_value=(f"Identity created: {expected}", "")
        ):
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

    def test_migrate_up(self, command_line: CommandLine) -> None:
        with patch.object(command_line, "_run_cmd") as mocked_run_cmd:
            command_line.migrate_up("dsn", 60)

        mocked_run_cmd.assert_called_once_with(
            [
                "identity-platform-admin-ui",
                "migrate",
                "--dsn",
                "dsn",
                "up",
            ],
            exec_config=CmdExecConfig(service_context="admin-ui", timeout=60),
        )

    @pytest.mark.parametrize(
        "error",
        [ExecError(["cmd"], 1, "stdout", "stderr"), Error("error")],
    )
    def test_migrate_up_failed(self, command_line: CommandLine, error: Error) -> None:
        with (
            patch.object(command_line, "_run_cmd", side_effect=error),
            pytest.raises(MigrationError),
        ):
            command_line.migrate_up("dsn", 60)

    @pytest.mark.parametrize(
        "version,expected_args",
        [
            (
                None,
                [
                    "identity-platform-admin-ui",
                    "migrate",
                    "--dsn",
                    "dsn",
                    "down",
                ],
            ),
            (
                "1.0",
                [
                    "identity-platform-admin-ui",
                    "migrate",
                    "--dsn",
                    "dsn",
                    "down",
                    "1.0",
                ],
            ),
        ],
    )
    def test_migrate_down(
        self, command_line: CommandLine, version: str | None, expected_args: list[str]
    ) -> None:
        with patch.object(command_line, "_run_cmd") as mocked_run_cmd:
            command_line.migrate_down("dsn", version, timeout=60)

        mocked_run_cmd.assert_called_once_with(
            expected_args,
            exec_config=CmdExecConfig(service_context="admin-ui", timeout=60),
        )

    @pytest.mark.parametrize(
        "error",
        [ExecError(["cmd"], 1, "stdout", "stderr"), Error("error")],
    )
    def test_migrate_down_failed(self, command_line: CommandLine, error: Error) -> None:
        with (
            patch.object(command_line, "_run_cmd", side_effect=error),
            pytest.raises(MigrationError),
        ):
            command_line.migrate_down("dsn", timeout=60)

    def test_migrate_status(self, command_line: CommandLine) -> None:
        expected = "status"
        with patch.object(command_line, "_run_cmd", return_value=("", expected)) as mocked_run_cmd:
            actual = command_line.migrate_status("dsn")

        assert actual == expected
        mocked_run_cmd.assert_called_once_with(
            [
                "identity-platform-admin-ui",
                "migrate",
                "--dsn",
                "dsn",
                "status",
            ],
            exec_config=CmdExecConfig(service_context="admin-ui"),
        )

    @pytest.mark.parametrize(
        "error",
        [ExecError(["cmd"], 1, "stdout", "stderr"), Error("error")],
    )
    def test_migrate_status_failed(self, command_line: CommandLine, error: Error) -> None:
        with patch.object(command_line, "_run_cmd", side_effect=error):
            actual = command_line.migrate_status("dsn")

        assert actual is None

    def test_run_cmd(self, mocked_container: MagicMock, command_line: CommandLine) -> None:
        cmd, options, expected = (
            ["cmd"],
            CmdExecConfig(environment={"ENV": "VAR"}, timeout=60, stdin="stdin"),
            ("stdout", "stderr"),
        )

        mocked_process = MagicMock(wait_output=MagicMock(return_value=expected))
        mocked_container.exec.return_value = mocked_process

        actual = command_line._run_cmd(cmd, exec_config=options)

        assert actual == expected
        mocked_container.exec.assert_called_once_with(cmd, **asdict(options))
