#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
import os
from typing import Callable, Optional

import pytest
import requests
from conftest import (
    ADMIN_SERVICE_APP,
    ADMIN_SERVICE_IMAGE,
    DB_APP,
    OATHKEEPER_APP,
    OPENFGA_APP,
    remove_integration,
)
from juju.application import Application
from oauth_tools import (
    ExternalIdpService,
    access_application_login_page,
    complete_auth_code_login,
    deploy_identity_bundle,
    get_reverse_proxy_app_url,
    verify_page_loads,
)
from playwright.async_api._generated import BrowserContext, Page
from pytest_operator.plugin import OpsTest

from constants import (
    CERTIFICATE_TRANSFER_INTEGRATION_NAME,
    HYDRA_ENDPOINTS_INTEGRATION_NAME,
    INGRESS_INTEGRATION_NAME,
    KRATOS_INFO_INTEGRATION_NAME,
    OPENFGA_INTEGRATION_NAME,
)

pytest_plugins = ["oauth_tools.fixtures"]
logger = logging.getLogger(__name__)


@pytest.mark.skip_if_deployed
@pytest.mark.abort_on_fail
async def test_build_and_deploy(
    ops_test: OpsTest,
    hydra_app_name: str,
    kratos_app_name: str,
    public_traefik_app_name: str,
    self_signed_certificates_app_name: str,
    ext_idp_service: ExternalIdpService,
) -> None:
    charm_file = await ops_test.build_charm(".")
    resources = {"oci-image": ADMIN_SERVICE_IMAGE}
    await ops_test.model.deploy(
        str(charm_file),
        resources=resources,
        application_name=ADMIN_SERVICE_APP,
        trust=True,
        series="jammy",
    )

    # Deploy dependencies
    await deploy_identity_bundle(
        ops_test=ops_test,
        bundle_channel="latest/edge",
        ext_idp_service=ext_idp_service,
    )

    await ops_test.model.deploy(
        entity_url=OPENFGA_APP,
        channel="latest/edge",
        series="jammy",
        trust=True,
    )
    await ops_test.model.integrate(OPENFGA_APP, DB_APP)
    await ops_test.model.wait_for_idle(apps=[OPENFGA_APP, DB_APP], status="active", timeout=5 * 60)

    await ops_test.model.deploy(
        entity_url=OATHKEEPER_APP,
        channel="latest/edge",
        series="jammy",
        trust=True,
    )

    # Integrate with dependencies
    await ops_test.model.integrate(
        f"{ADMIN_SERVICE_APP}:kratos-info",
        kratos_app_name,
    )
    await ops_test.model.integrate(
        f"{ADMIN_SERVICE_APP}:hydra-endpoint-info",
        hydra_app_name,
    )
    await ops_test.model.integrate(ADMIN_SERVICE_APP, OPENFGA_APP)
    await ops_test.model.integrate(ADMIN_SERVICE_APP, public_traefik_app_name)
    await ops_test.model.integrate(f"{ADMIN_SERVICE_APP}:oauth", hydra_app_name)
    await ops_test.model.integrate(ADMIN_SERVICE_APP, self_signed_certificates_app_name)
    await ops_test.model.integrate(f"{ADMIN_SERVICE_APP}:oathkeeper-info", OATHKEEPER_APP)

    await ops_test.model.wait_for_idle(
        status="active",
        timeout=10 * 60,
    )


def test_kratos_integration(leader_kratos_integration_data: Optional[dict]) -> None:
    assert leader_kratos_integration_data
    assert all(leader_kratos_integration_data.values())


def test_hydra_endpoint_integration(
    leader_hydra_endpoint_integration_data: Optional[dict],
) -> None:
    assert leader_hydra_endpoint_integration_data
    assert all(leader_hydra_endpoint_integration_data.values())


def test_openfga_integration(leader_openfga_integration_data: Optional[dict]) -> None:
    assert leader_openfga_integration_data
    assert all(leader_openfga_integration_data.values())


def test_oathkeeper_integration(leader_oathkeeper_integration_data: Optional[dict]) -> None:
    assert leader_oathkeeper_integration_data
    assert all(leader_oathkeeper_integration_data.values())


def test_ingress_integration(
    ops_test: OpsTest, leader_ingress_integration_data: Optional[dict]
) -> None:
    assert leader_ingress_integration_data
    assert leader_ingress_integration_data["ingress"]

    data = json.loads(leader_ingress_integration_data["ingress"])
    assert f"{ops_test.model_name}-{ADMIN_SERVICE_APP}" in data["url"]


def test_oauth_integration(leader_oauth_integration_data: Optional[dict]) -> None:
    assert leader_oauth_integration_data
    assert all(leader_oauth_integration_data.values())


def test_peer_integration(
    leader_peer_integration_data: Optional[dict],
    admin_service_version: str,
) -> None:
    assert leader_peer_integration_data
    assert leader_peer_integration_data[admin_service_version]

    openfga_model = json.loads(leader_peer_integration_data[admin_service_version])
    assert openfga_model["openfga_model_id"]


async def test_scale_up(
    ops_test: OpsTest,
    admin_service_application: Application,
    leader_openfga_integration_data: Optional[dict],
    leader_peer_integration_data: Optional[dict],
    app_integration_data: Callable,
) -> None:
    target_unit_number = 2

    await admin_service_application.scale(target_unit_number)

    await ops_test.model.wait_for_idle(
        apps=[ADMIN_SERVICE_APP],
        status="active",
        timeout=5 * 60,
        wait_for_exact_units=target_unit_number,
    )

    follower_peer_data = app_integration_data(ADMIN_SERVICE_APP, ADMIN_SERVICE_APP, 1)
    assert follower_peer_data
    assert leader_peer_integration_data == follower_peer_data

    follower_openfga_data = app_integration_data(ADMIN_SERVICE_APP, "openfga", 1)
    assert follower_openfga_data
    assert follower_openfga_data == leader_openfga_integration_data


async def test_oauth_login_with_identity_bundle(
    ops_test: OpsTest,
    page: Page,
    context: BrowserContext,
    public_traefik_app_name: str,
    ext_idp_service: ExternalIdpService,
) -> None:
    admin_ui_proxy = await get_reverse_proxy_app_url(
        ops_test, public_traefik_app_name, ADMIN_SERVICE_APP
    )
    login_url = os.path.join(admin_ui_proxy, "api/v0/auth")
    me_url = os.path.join(admin_ui_proxy, "api/v0/auth/me")

    await access_application_login_page(page=page, url=login_url)

    await complete_auth_code_login(page=page, ops_test=ops_test, ext_idp_service=ext_idp_service)

    redirect_url = os.path.join(admin_ui_proxy, "ui/")
    await verify_page_loads(page=page, url=redirect_url)

    # Validate that the cookies have been set
    cookies = {c["name"]: c["value"] for c in await context.cookies(me_url)}
    user = requests.get(me_url, cookies=cookies, verify=False)

    assert user.json()
    assert user.json()["email"] == ext_idp_service.user_email


async def test_remove_integration_openfga(
    ops_test: OpsTest,
    admin_service_application: Application,
) -> None:
    async with remove_integration(ops_test, OPENFGA_APP, OPENFGA_INTEGRATION_NAME):
        assert "blocked" == admin_service_application.status


async def test_remove_integration_kratos_info(
    ops_test: OpsTest,
    kratos_app_name: str,
    admin_service_application: Application,
) -> None:
    async with remove_integration(ops_test, kratos_app_name, KRATOS_INFO_INTEGRATION_NAME):
        assert "blocked" == admin_service_application.status


async def test_remove_integration_hydra_endpoint_info(
    ops_test: OpsTest,
    hydra_app_name: str,
    admin_service_application: Application,
) -> None:
    async with remove_integration(ops_test, hydra_app_name, HYDRA_ENDPOINTS_INTEGRATION_NAME):
        assert "blocked" == admin_service_application.status


async def test_remove_integration_ingress(
    ops_test: OpsTest,
    public_traefik_app_name: str,
    admin_service_application: Application,
) -> None:
    async with remove_integration(ops_test, public_traefik_app_name, INGRESS_INTEGRATION_NAME):
        assert "blocked" == admin_service_application.status


async def test_remove_integration_certificate_transfer(
    ops_test: OpsTest,
    self_signed_certificates_app_name: str,
    admin_service_application: Application,
) -> None:
    async with remove_integration(
        ops_test, self_signed_certificates_app_name, CERTIFICATE_TRANSFER_INTEGRATION_NAME
    ):
        assert "blocked" == admin_service_application.status


async def test_scale_down(
    ops_test: OpsTest,
    admin_service_application: Application,
    leader_openfga_integration_data: Optional[dict],
    leader_peer_integration_data: Optional[dict],
) -> None:
    target_unit_num = 1

    await admin_service_application.scale(target_unit_num)

    await ops_test.model.wait_for_idle(
        apps=[ADMIN_SERVICE_APP],
        status="active",
        timeout=5 * 60,
        wait_for_exact_units=target_unit_num,
    )

    assert leader_peer_integration_data
    assert leader_openfga_integration_data
