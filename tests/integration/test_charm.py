#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
from typing import Callable, Optional

import pytest
from conftest import (
    ADMIN_SERVICE_APP,
    ADMIN_SERVICE_IMAGE,
    DB_APP,
    OATHKEEPER_APP,
    OPENFGA_APP,
    remove_integration,
)
from juju.application import Application
from oauth_tools import ExternalIdpService, deploy_identity_bundle
from pytest_operator.plugin import OpsTest

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
    await ops_test.model.integrate(f"{ADMIN_SERVICE_APP}:oathkeeper-info", OATHKEEPER_APP)
    await ops_test.model.integrate(ADMIN_SERVICE_APP, public_traefik_app_name)
    await ops_test.model.integrate(f"{ADMIN_SERVICE_APP}:oauth", hydra_app_name)
    await ops_test.model.integrate(ADMIN_SERVICE_APP, self_signed_certificates_app_name)

    await ops_test.model.wait_for_idle(
        status="active",
        timeout=1000,
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
        timeout=1000,
        wait_for_exact_units=target_unit_number,
    )

    follower_peer_data = app_integration_data(ADMIN_SERVICE_APP, ADMIN_SERVICE_APP, 1)
    assert follower_peer_data
    assert leader_peer_integration_data == follower_peer_data

    follower_openfga_data = app_integration_data(ADMIN_SERVICE_APP, "openfga", 1)
    assert follower_openfga_data
    assert follower_openfga_data == leader_openfga_integration_data


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
        timeout=1000,
        wait_for_exact_units=target_unit_num,
    )

    assert leader_peer_integration_data
    assert leader_openfga_integration_data


async def test_remove_integration_with_openfga(
    ops_test: OpsTest,
    admin_service_application: Application,
) -> None:
    async with remove_integration(ops_test, OPENFGA_APP):
        assert "blocked" == admin_service_application.status


@pytest.mark.xfail(reason="not implemented yet")
async def test_remove_integration_with_kratos(
    ops_test: OpsTest,
    kratos_app_name: str,
    admin_service_application: Application,
) -> None:
    async with remove_integration(ops_test, kratos_app_name):
        assert "blocked" == admin_service_application.status


@pytest.mark.xfail(reason="not implemented yet")
async def test_remove_integration_with_hydra(
    ops_test: OpsTest,
    hydra_app_name: str,
    admin_service_application: Application,
) -> None:
    async with remove_integration(ops_test, hydra_app_name):
        assert "blocked" == admin_service_application.status


@pytest.mark.xfail(reason="not implemented yet")
async def test_remove_integration_with_ingress(
    ops_test: OpsTest,
    public_traefik_app_name: str,
    admin_service_application: Application,
) -> None:
    async with remove_integration(ops_test, public_traefik_app_name):
        assert "blocked" == admin_service_application.status
