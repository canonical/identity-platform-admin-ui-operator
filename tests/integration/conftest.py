# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.


import functools
import re
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Callable, Optional

import pytest
import yaml
from juju.application import Application
from pytest_operator.plugin import OpsTest

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
ADMIN_SERVICE_APP = METADATA["name"]
ADMIN_SERVICE_IMAGE = METADATA["resources"]["oci-image"]["upstream-source"]
DB_APP = "postgresql-k8s"
HYDRA_APP = "hydra"
KRATOS_APP = "kratos"
OATHKEEPER_APP = "oathkeeper"
OPENFGA_APP = "openfga-k8s"
TRAEFIK_APP = "traefik-k8s"


def get_unit_data(unit_name: str, model_name: str) -> dict:
    res = subprocess.run(
        ["juju", "show-unit", unit_name, "-m", model_name],
        check=True,
        text=True,
        capture_output=True,
    )
    cmd_output = yaml.safe_load(res.stdout)
    return cmd_output[unit_name]


def get_integration_data(
    model_name: str,
    app_name: str,
    integration_name: str,
    unit_num: int = 0,
) -> Optional[dict]:
    unit_data = get_unit_data(f"{app_name}/{unit_num}", model_name)
    return next(
        (
            integration
            for integration in unit_data["relation-info"]
            if integration["endpoint"] == integration_name
        ),
        None,
    )


def get_app_integration_data(
    model_name: str, app_name: str, integration_name: str, unit_num: int = 0
) -> Optional[dict]:
    data = get_integration_data(model_name, app_name, integration_name, unit_num)
    return data["application-data"] if data else None


@pytest.fixture
def app_integration_data(ops_test: OpsTest) -> Callable:
    return functools.partial(get_app_integration_data, ops_test.model_name)


@pytest.fixture
def leader_kratos_integration_data(app_integration_data: Callable) -> Optional[dict]:
    return app_integration_data(ADMIN_SERVICE_APP, "kratos-info")


@pytest.fixture
def leader_hydra_endpoint_integration_data(app_integration_data: Callable) -> Optional[dict]:
    return app_integration_data(ADMIN_SERVICE_APP, "hydra-endpoint-info")


@pytest.fixture
def leader_openfga_integration_data(app_integration_data: Callable) -> Optional[dict]:
    return app_integration_data(ADMIN_SERVICE_APP, "openfga")


@pytest.fixture
def leader_oathkeeper_integration_data(app_integration_data: Callable) -> Optional[dict]:
    return app_integration_data(ADMIN_SERVICE_APP, "oathkeeper-info")


@pytest.fixture
def leader_ingress_integration_data(app_integration_data: Callable) -> Optional[dict]:
    return app_integration_data(ADMIN_SERVICE_APP, "ingress")


@pytest.fixture
def leader_peer_integration_data(app_integration_data: Callable) -> Optional[dict]:
    return app_integration_data(ADMIN_SERVICE_APP, ADMIN_SERVICE_APP)


@pytest.fixture
def leader_oauth_integration_data(app_integration_data: Callable) -> Optional[dict]:
    return app_integration_data(ADMIN_SERVICE_APP, "oauth")


@pytest.fixture
def admin_service_application(ops_test: OpsTest) -> Application:
    return ops_test.model.applications[ADMIN_SERVICE_APP]


@pytest.fixture(scope="session")
def admin_service_version() -> str:
    matched = re.search(r"v(?P<version>\d+\.\d+\.\d+)", ADMIN_SERVICE_IMAGE)
    return matched.group("version") if matched else ""


@asynccontextmanager
async def remove_integration(
    ops_test: OpsTest, remote_app_name: str
) -> AsyncGenerator[None, None]:
    remove_integration_cmd = (f"remove-relation {ADMIN_SERVICE_APP} {remote_app_name}").split()
    await ops_test.juju(*remove_integration_cmd)
    await ops_test.model.wait_for_idle(
        apps=[remote_app_name],
        status="active",
    )

    try:
        yield
    finally:
        await ops_test.model.integrate(ADMIN_SERVICE_APP, remote_app_name)
        await ops_test.model.wait_for_idle(
            apps=[ADMIN_SERVICE_APP, remote_app_name],
            status="active",
        )
