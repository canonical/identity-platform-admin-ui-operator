# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.


import functools
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Callable, Optional

import pytest
import pytest_asyncio
import yaml
from juju.application import Application
from pytest_operator.plugin import OpsTest

METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
ADMIN_SERVICE_APP = METADATA["name"]
ADMIN_SERVICE_IMAGE = METADATA["resources"]["oci-image"]["upstream-source"]
DB_APP = "postgresql-k8s"
OATHKEEPER_APP = "oathkeeper"
OPENFGA_APP = "openfga-k8s"


async def integrate_dependencies(
    ops_test: OpsTest,
    request: pytest.FixtureRequest,
) -> None:
    kratos_app_name = request.getfixturevalue("kratos_app_name")
    hydra_app_name = request.getfixturevalue("hydra_app_name")
    public_ingress_name = request.getfixturevalue("public_traefik_app_name")
    self_signed_cert_app_name = request.getfixturevalue("self_signed_certificates_app_name")

    await ops_test.model.integrate(
        f"{ADMIN_SERVICE_APP}:kratos-info",
        kratos_app_name,
    )
    await ops_test.model.integrate(
        f"{ADMIN_SERVICE_APP}:hydra-endpoint-info",
        hydra_app_name,
    )
    await ops_test.model.integrate(ADMIN_SERVICE_APP, OPENFGA_APP)
    await ops_test.model.integrate(ADMIN_SERVICE_APP, public_ingress_name)
    await ops_test.model.integrate(f"{ADMIN_SERVICE_APP}:oauth", hydra_app_name)
    await ops_test.model.integrate(ADMIN_SERVICE_APP, self_signed_cert_app_name)
    await ops_test.model.integrate(f"{ADMIN_SERVICE_APP}:oathkeeper-info", OATHKEEPER_APP)


async def get_unit_data(ops_test: OpsTest, unit_name: str) -> dict:
    show_unit_cmd = f"show-unit {unit_name}".split()
    _, stdout, _ = await ops_test.juju(*show_unit_cmd)
    cmd_output = yaml.safe_load(stdout)
    return cmd_output[unit_name]


async def get_integration_data(
    ops_test: OpsTest, app_name: str, integration_name: str, unit_num: int = 0
) -> Optional[dict]:
    data = await get_unit_data(ops_test, f"{app_name}/{unit_num}")
    return next(
        (
            integration
            for integration in data["relation-info"]
            if integration["endpoint"] == integration_name
        ),
        None,
    )


async def get_app_integration_data(
    ops_test: OpsTest,
    app_name: str,
    integration_name: str,
    unit_num: int = 0,
) -> Optional[dict]:
    data = await get_integration_data(ops_test, app_name, integration_name, unit_num)
    return data["application-data"] if data else None


@pytest_asyncio.fixture
async def app_integration_data(ops_test: OpsTest) -> Callable:
    return functools.partial(get_app_integration_data, ops_test)


@pytest_asyncio.fixture
async def leader_kratos_integration_data(app_integration_data: Callable) -> Optional[dict]:
    return await app_integration_data(ADMIN_SERVICE_APP, "kratos-info")


@pytest_asyncio.fixture
async def leader_hydra_endpoint_integration_data(app_integration_data: Callable) -> Optional[dict]:
    return await app_integration_data(ADMIN_SERVICE_APP, "hydra-endpoint-info")


@pytest_asyncio.fixture
async def leader_openfga_integration_data(app_integration_data: Callable) -> Optional[dict]:
    return await app_integration_data(ADMIN_SERVICE_APP, "openfga")


@pytest_asyncio.fixture
async def leader_oathkeeper_integration_data(app_integration_data: Callable) -> Optional[dict]:
    return await app_integration_data(ADMIN_SERVICE_APP, "oathkeeper-info")


@pytest_asyncio.fixture
async def leader_ingress_integration_data(app_integration_data: Callable) -> Optional[dict]:
    return await app_integration_data(ADMIN_SERVICE_APP, "ingress")


@pytest_asyncio.fixture
async def leader_peer_integration_data(app_integration_data: Callable) -> Optional[dict]:
    return await app_integration_data(ADMIN_SERVICE_APP, ADMIN_SERVICE_APP)


@pytest_asyncio.fixture
async def leader_oauth_integration_data(app_integration_data: Callable) -> Optional[dict]:
    return await app_integration_data(ADMIN_SERVICE_APP, "oauth")


@pytest.fixture
def admin_service_application(ops_test: OpsTest) -> Application:
    return ops_test.model.applications[ADMIN_SERVICE_APP]


@pytest.fixture(scope="session")
def admin_service_version() -> str:
    matched = re.search(r"v(?P<version>\d+\.\d+\.\d+)", ADMIN_SERVICE_IMAGE)
    return matched.group("version") if matched else ""


@pytest_asyncio.fixture(scope="module")
async def local_charm(ops_test: OpsTest) -> Path:
    return await ops_test.build_charm(".")


@asynccontextmanager
async def remove_integration(
    ops_test: OpsTest, remote_app_name: str, integration_name: str
) -> AsyncGenerator[None, None]:
    remove_integration_cmd = (
        f"remove-relation {ADMIN_SERVICE_APP}:{integration_name} {remote_app_name}"
    ).split()
    await ops_test.juju(*remove_integration_cmd)
    await ops_test.model.wait_for_idle(
        apps=[remote_app_name],
        status="active",
    )

    try:
        yield
    finally:
        await ops_test.model.integrate(f"{ADMIN_SERVICE_APP}:{integration_name}", remote_app_name)
        await ops_test.model.wait_for_idle(
            apps=[ADMIN_SERVICE_APP, remote_app_name],
            status="active",
        )
