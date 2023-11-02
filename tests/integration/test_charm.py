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

    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(
            apps=[APP_NAME],
            status="active",
            raise_on_blocked=True,
            timeout=1000,
        )
        assert ops_test.model.applications[APP_NAME].units[0].workload_status == "active"


async def test_ingress_relation(ops_test: OpsTest):
    await ops_test.model.deploy(
        TRAEFIK,
        channel="latest/edge",
        config={"external_hostname": "some_hostname"},
    )

    await ops_test.model.add_relation(f"{APP_NAME}:ingress", TRAEFIK)

    await ops_test.model.wait_for_idle(
        apps=[TRAEFIK],
        status="active",
        raise_on_blocked=True,
        timeout=1000,
    )


async def test_has_ingress(ops_test: OpsTest):
    """Get the traefik address and try to reach identity-platform-admin-ui."""
    public_address = await get_unit_address(ops_test, TRAEFIK, 0)

    resp = requests.get(f"http://{public_address}/{ops_test.model.name}-{APP_NAME}/api/v0/status")

    assert resp.status_code == 200
