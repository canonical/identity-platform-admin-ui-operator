#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
from pathlib import Path

import pytest
import requests
import yaml
from oauth_tools import ExternalIdpService, complete_auth_code_login, deploy_identity_bundle
from playwright.async_api._generated import Page
from pytest_operator.plugin import OpsTest

from constants import OAUTH_CALLBACK_PATH

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
APP_NAME = METADATA["name"]
DB_APP = "postgresql-k8s"
OATHKEEPER = "oathkeeper"
OPENFGA = "openfga-k8s"

pytest_plugins = ["oauth_tools.fixtures"]


async def get_unit_address(ops_test: OpsTest, app_name: str, unit_num: int) -> str:
    """Get private address of a unit."""
    status = await ops_test.model.get_status()  # noqa: F821
    return status["applications"][app_name]["units"][f"{app_name}/{unit_num}"]["address"]


async def get_app_address(ops_test: OpsTest, app_name: str) -> str:
    """Get address of an app."""
    status = await ops_test.model.get_status()  # noqa: F821
    return status["applications"][app_name]["public-address"]


async def get_reverse_proxy_app_url(
    ops_test: OpsTest, ingress_app_name: str, app_name: str
) -> str:
    address = await get_app_address(ops_test, ingress_app_name)
    return f"https://{address}/{ops_test.model.name}-{app_name}/"


@pytest.mark.abort_on_fail
async def test_build_and_deploy(
    ops_test: OpsTest,
    hydra_app_name: str,
    kratos_app_name: str,
    ext_idp_service: ExternalIdpService,
):
    """Build the charm-under-test and deploy it.

    Assert on the unit status before any relations/configurations take place.
    """
    charm = await ops_test.build_charm(".")
    resources = {"oci-image": METADATA["resources"]["oci-image"]["upstream-source"]}
    await ops_test.model.deploy(
        charm, resources=resources, application_name=APP_NAME, trust=True, series="jammy"
    )

    # Deploy dependencies
    await deploy_identity_bundle(
        ops_test=ops_test, bundle_channel="latest/edge", ext_idp_service=ext_idp_service
    )
    await ops_test.model.deploy(
        entity_url=OPENFGA,
        channel="latest/edge",
        series="jammy",
        trust=True,
    )

    await ops_test.model.integrate(OPENFGA, DB_APP)
    await ops_test.model.integrate(f"{APP_NAME}:hydra-endpoint-info", hydra_app_name)
    await ops_test.model.integrate(f"{APP_NAME}:kratos-info", kratos_app_name)
    await ops_test.model.integrate(APP_NAME, OPENFGA)

    await ops_test.model.wait_for_idle(
        status="active",
        raise_on_blocked=False,
        timeout=1000,
    )


async def test_ingress_relation(ops_test: OpsTest, public_traefik_app_name: str):
    await ops_test.model.add_relation(f"{APP_NAME}:ingress", public_traefik_app_name)

    await ops_test.model.wait_for_idle(
        apps=[APP_NAME, public_traefik_app_name],
        status="active",
        raise_on_blocked=True,
        timeout=1000,
    )


async def test_has_ingress(ops_test: OpsTest, public_traefik_app_name: str):
    """Get the traefik address and try to reach identity-platform-admin-ui."""
    public_address = await get_unit_address(ops_test, public_traefik_app_name, 0)

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
        raise_on_error=False,
        timeout=1000,
    )


async def test_oauth_relation(
    ops_test: OpsTest, hydra_app_name: str, self_signed_certificates_app_name: str
):
    await ops_test.model.add_relation(
        f"{APP_NAME}:receive-ca-cert", self_signed_certificates_app_name
    )
    await ops_test.model.add_relation(f"{APP_NAME}:oauth", hydra_app_name)

    await ops_test.model.wait_for_idle(
        apps=[APP_NAME, hydra_app_name],
        status="active",
        raise_on_blocked=False,
        raise_on_error=False,
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
        wait_for_exact_units=2,
    )


async def test_login(
    ops_test: OpsTest,
    page: Page,
    ext_idp_service: ExternalIdpService,
    public_traefik_app_name: str,
) -> None:
    url = await get_reverse_proxy_app_url(ops_test, public_traefik_app_name, APP_NAME)
    redirect_uri = os.path.join(url, OAUTH_CALLBACK_PATH)

    await page.goto(os.path.join(url, "api/v0/auth"))

    await complete_auth_code_login(page, ops_test, ext_idp_service)

    # TODO: Add response and session validation
    await page.wait_for_url(redirect_uri + "?*")


async def test_scale_down(ops_test: OpsTest) -> None:
    """Check that Admin UI works after it is scaled down."""
    app = ops_test.model.applications[APP_NAME]

    await app.scale(1)

    await ops_test.model.wait_for_idle(
        apps=[APP_NAME],
        status="active",
        raise_on_blocked=False,
        timeout=1000,
    )
