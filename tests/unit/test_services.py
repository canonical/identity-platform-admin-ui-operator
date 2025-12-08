# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more about testing at: https://juju.is/docs/sdk/testing

from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from constants import ADMIN_SERVICE_PORT, CA_CERT_DIR_PATH, WORKLOAD_CONTAINER
from env_vars import EnvVarConvertible
from exceptions import PebbleServiceError
from services import DEFAULT_CONTAINER_ENV, WORKLOAD_SERVICE, PebbleService, WorkloadService


class TestWorkloadService:
    @pytest.fixture
    def workload_service(
        self, mocked_container: MagicMock, mocked_unit: MagicMock
    ) -> WorkloadService:
        return WorkloadService(mocked_unit)

    def test_get_version(self, workload_service: WorkloadService) -> None:
        with patch("cli.CommandLine.get_admin_service_version", return_value="1.0.0"):
            assert workload_service.version == "1.0.0"

    def test_set_version(self, mocked_unit: MagicMock, workload_service: WorkloadService) -> None:
        workload_service.version = "1.0.0"
        mocked_unit.set_workload_version.assert_called_once_with("1.0.0")

    def test_set_empty_version(
        self, mocked_unit: MagicMock, workload_service: WorkloadService
    ) -> None:
        workload_service.version = ""
        mocked_unit.set_workload_version.assert_not_called()

    def test_set_version_with_error(
        self,
        mocked_unit: MagicMock,
        workload_service: WorkloadService,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        error_msg = "Error from unit"
        mocked_unit.set_workload_version.side_effect = Exception(error_msg)

        with caplog.at_level("ERROR"):
            workload_service.version = "2.0.0"

        mocked_unit.set_workload_version.assert_called_once_with("2.0.0")
        assert f"Failed to set workload version: {error_msg}" in caplog.text

    def test_open_port(self, mocked_unit: MagicMock, workload_service: WorkloadService) -> None:
        workload_service.open_port()
        mocked_unit.open_port.assert_called_once_with(protocol="tcp", port=ADMIN_SERVICE_PORT)

    def test_prepare_dir(
        self, mocked_container: MagicMock, workload_service: WorkloadService
    ) -> None:
        mocked_container.isdir.return_value = False
        workload_service.prepare_dir("some_dir")
        mocked_container.make_dir.assert_called_once_with(path="some_dir", make_parents=True)

    def test_push_ca_certs(
        self, mocked_container: MagicMock, workload_service: WorkloadService
    ) -> None:
        ca_certs = "ca_certs"
        workload_service.push_ca_certs(ca_certs)
        mocked_container.push.assert_called_once_with(
            CA_CERT_DIR_PATH / "ca-certificates.crt", ca_certs, make_dirs=True
        )

    @pytest.mark.parametrize("model_id, expected", [("model_id", "model_id"), (None, "")])
    def test_create_openfga_model(
        self, workload_service: WorkloadService, model_id: Optional[str], expected: str
    ) -> None:
        openfga_data = MagicMock(
            url="http://api.openfga.com", api_token="token", store_id="store_id"
        )
        with patch("cli.CommandLine.create_openfga_model", return_value=model_id):
            actual = workload_service.create_openfga_model(openfga_data)
            assert actual == expected


class TestPebbleService:
    @pytest.fixture
    def pebble_service(self, mocked_container: MagicMock, mocked_unit: MagicMock) -> PebbleService:
        return PebbleService(mocked_unit)

    @patch("ops.pebble.Layer")
    def test_plan(
        self, mocked_layer: MagicMock, mocked_container: MagicMock, pebble_service: PebbleService
    ) -> None:
        pebble_service.plan(mocked_layer)

        mocked_container.add_layer.assert_called_once_with(
            WORKLOAD_CONTAINER, mocked_layer, combine=True
        )
        mocked_container.replan.assert_called_once()

    @patch("ops.pebble.Layer")
    def test_plan_failure(
        self,
        mocked_layer: MagicMock,
        mocked_container: MagicMock,
        pebble_service: PebbleService,
    ) -> None:
        mocked_container.replan.side_effect = Exception

        with pytest.raises(PebbleServiceError):
            pebble_service.plan(mocked_layer)

        mocked_container.add_layer.assert_called_once_with(
            WORKLOAD_CONTAINER, mocked_layer, combine=True
        )
        mocked_container.replan.assert_called_once()

    def test_render_pebble_layer(self, pebble_service: PebbleService) -> None:
        data_source = MagicMock(spec=EnvVarConvertible)
        data_source.to_env_vars.return_value = {"key1": "value1"}

        another_data_source = MagicMock(spec=EnvVarConvertible)
        another_data_source.to_env_vars.return_value = {"key2": "value2"}

        expected = {
            **DEFAULT_CONTAINER_ENV,
            "key1": "value1",
            "key2": "value2",
        }

        layer = pebble_service.render_pebble_layer(data_source, another_data_source)

        assert layer.to_dict()["services"][WORKLOAD_SERVICE]["environment"] == expected
