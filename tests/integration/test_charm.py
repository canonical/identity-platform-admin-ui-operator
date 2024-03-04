#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from pathlib import Path

import pytest
import requests
import yaml
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
APP_NAME = METADATA["name"]
TRAEFIK = "traefik-k8s"
DB_APP = "postgresql-k8s"
HYDRA = "hydra"
KRATOS = "kratos"
OATHKEEPER = "oathkeeper"
OPENFGA = "openfga-k8s"


async def get_unit_address(ops_test: OpsTest, app_name: str, unit_num: int) -> str:
    """Get private address of a unit."""
    status = await ops_test.model.get_status()  # noqa: F821
    return status["applications"][app_name]["units"][f"{app_name}/{unit_num}"]["address"]


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest):
    """Build the charm-under-test and deploy it.

    Assert on the unit status before any relations/configurations take place.
    """
    charm = await ops_test.build_charm(".")
    resources = {"oci-image": METADATA["resources"]["oci-image"]["upstream-source"]}
    await ops_test.model.deploy(
        charm, resources=resources, application_name=APP_NAME, trust=True, series="jammy"
    )

    # Deploy dependencies
    await ops_test.model.deploy(
        entity_url=DB_APP,
        channel="14/stable",
        series="jammy",
        trust=True,
    )
    await ops_test.model.deploy(
        TRAEFIK,
        channel="latest/edge",
        config={"external_hostname": "some_hostname"},
    )
    await ops_test.model.deploy(
        entity_url=OPENFGA,
        channel="latest/edge",
        series="jammy",
        trust=True,
    )
    await ops_test.model.deploy(
        entity_url=KRATOS,
        channel="latest/edge",
        series="jammy",
        trust=True,
    )
    await ops_test.model.deploy(
        entity_url=HYDRA,
        channel="latest/edge",
        series="jammy",
        trust=True,
    )

    await ops_test.model.integrate(OPENFGA, DB_APP)
    await ops_test.model.wait_for_idle([OPENFGA, DB_APP], status="active", timeout=1000)

    await ops_test.model.integrate(HYDRA, DB_APP)
    await ops_test.model.integrate(f"{HYDRA}:public-ingress", TRAEFIK)
    await ops_test.model.integrate(KRATOS, DB_APP)

    await ops_test.model.integrate(f"{APP_NAME}:hydra-endpoint-info", HYDRA)
    await ops_test.model.integrate(f"{APP_NAME}:kratos-info", KRATOS)
    await ops_test.model.integrate(APP_NAME, OPENFGA)

    await ops_test.model.wait_for_idle(
        apps=[APP_NAME, DB_APP, HYDRA, KRATOS, OPENFGA],
        status="active",
        raise_on_blocked=False,
        # TODO: Switch to true
        #  when https://github.com/canonical/openfga-operator/issues/25 is solved
        raise_on_error=False,
        timeout=1000,
    )


async def test_ingress_relation(ops_test: OpsTest):
    await ops_test.model.add_relation(f"{APP_NAME}:ingress", TRAEFIK)

    await ops_test.model.wait_for_idle(
        apps=[APP_NAME, TRAEFIK],
        status="active",
        raise_on_blocked=True,
        timeout=1000,
    )


async def test_has_ingress(ops_test: OpsTest):
    """Get the traefik address and try to reach identity-platform-admin-ui."""
    public_address = await get_unit_address(ops_test, TRAEFIK, 0)

    resp = requests.get(f"http://{public_address}/{ops_test.model.name}-{APP_NAME}/api/v0/status")

    assert resp.status_code == 200


async def test_oathkeeper_relation(ops_test: OpsTest):
    await ops_test.model.deploy(
        entity_url=OATHKEEPER,
        channel="latest/edge",
        series="jammy",
        trust=True,
    )

    await ops_test.model.add_relation(f"{APP_NAME}:oathkeeper-info", OATHKEEPER)

    await ops_test.model.wait_for_idle(
        apps=[APP_NAME, OATHKEEPER],
        status="active",
        raise_on_blocked=False,
        timeout=1000,
    )


async def test_scale_up(ops_test: OpsTest) -> None:
    """Check that Admin UI works after it is scaled up."""
    app = ops_test.model.applications[APP_NAME]

    await app.scale(2)

    await ops_test.model.wait_for_idle(
        apps=[APP_NAME],
        status="active",
        raise_on_blocked=False,
        timeout=1000,
        wait_for_active=True,
    )


async def test_scale_down(ops_test: OpsTest) -> None:
    """Check that Admin UI works after it is scaled down."""
    app = ops_test.model.applications[APP_NAME]

    await app.scale(1)

    await ops_test.model.wait_for_idle(
        apps=[APP_NAME],
        status="active",
        raise_on_blocked=False,
        timeout=1000,
        wait_for_active=True,
    )
