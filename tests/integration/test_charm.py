#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
from pathlib import Path
from typing import Optional

import jubilant
import pytest
from integration.conftest import (
    integrate_dependencies,
)
from integration.constants import (
    ADMIN_SERVICE_APP,
    ADMIN_SERVICE_IMAGE,
    CERTIFICATE_TRANSFER_INTEGRATION_NAME,
    DATABASE_INTEGRATION_NAME,
    DB_APP,
    HYDRA_ENDPOINTS_INTEGRATION_NAME,
    INGRESS_INTEGRATION_NAME,
    KRATOS_INFO_INTEGRATION_NAME,
    MAIL_APP,
    MAIL_SMTP_PORT,
    OPENFGA_APP,
    OPENFGA_INTEGRATION_NAME,
    OPENFGA_MODEL_ID,
    SMTP_INTEGRATOR_APP,
)
from integration.utils import (
    all_active,
    all_blocked,
    and_,
    any_error,
    remove_integration,
    unit_number,
)

logger = logging.getLogger(__name__)


@pytest.mark.setup
def test_build_and_deploy(
    juju: jubilant.Juju,
    local_charm: str,
    kratos_app_name: str,
    hydra_app_name: str,
    public_traefik_app_name: str,
    self_signed_certificates_app_name: str,
    mail_deployment: None,
) -> None:
    # Deploy dependencies
    bundle_path = Path(__file__).parent / "identity_bundle.yaml"
    juju.deploy(str(bundle_path), trust=True)

    # Deploy local charm
    juju.deploy(
        str(local_charm),
        app=ADMIN_SERVICE_APP,
        resources={"oci-image": ADMIN_SERVICE_IMAGE},
        trust=True,
    )

    juju.deploy(
        "openfga-k8s",
        channel="latest/edge",
        trust=True,
    )
    juju.integrate(OPENFGA_APP, DB_APP)

    # Wait for OpenFGA and DB to be ready before integrating with Admin UI
    juju.wait(
        ready=all_active(OPENFGA_APP, DB_APP),
        error=any_error(OPENFGA_APP, DB_APP),
        timeout=10 * 60,
    )

    juju.deploy(
        SMTP_INTEGRATOR_APP,
        channel="latest/edge",
        trust=True,
        config={
            "host": f"{MAIL_APP}.{juju.model}.svc.cluster.local",
            "port": str(MAIL_SMTP_PORT),
        },
    )

    # Integrate with dependencies
    integrate_dependencies(
        juju,
        kratos_app_name,
        hydra_app_name,
        public_traefik_app_name,
        self_signed_certificates_app_name,
    )

    juju.wait(
        ready=all_active(
            OPENFGA_APP,
            DB_APP,
            SMTP_INTEGRATOR_APP,
            kratos_app_name,
            hydra_app_name,
            public_traefik_app_name,
            self_signed_certificates_app_name,
        ),
        error=any_error(
            OPENFGA_APP,
            DB_APP,
            SMTP_INTEGRATOR_APP,
            kratos_app_name,
            hydra_app_name,
            public_traefik_app_name,
            self_signed_certificates_app_name,
        ),
        timeout=20 * 60,
    )

    juju.wait(
        ready=all_active(
            ADMIN_SERVICE_APP,
        ),
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


def test_ingress_integration(
    juju: jubilant.Juju, leader_ingress_integration_data: Optional[dict]
) -> None:
    assert leader_ingress_integration_data
    assert leader_ingress_integration_data["ingress"]

    data = json.loads(leader_ingress_integration_data["ingress"])
    assert f"{juju.model}-{ADMIN_SERVICE_APP}" in data["url"]


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
    assert openfga_model[OPENFGA_MODEL_ID]


def test_smtp_integration(
    juju: jubilant.Juju,
    leader_smtp_integration_data: Optional[dict],
) -> None:
    assert leader_smtp_integration_data
    assert leader_smtp_integration_data["host"] == f"{MAIL_APP}.{juju.model}.svc.cluster.local"
    assert leader_smtp_integration_data["port"] == str(MAIL_SMTP_PORT)


def test_database_integration(leader_database_integration_data: Optional[dict]) -> None:
    assert leader_database_integration_data


def test_create_identity_action(juju: jubilant.Juju) -> None:
    action = juju.run(
        f"{ADMIN_SERVICE_APP}/0",
        "create-identity",
        params={
            "schema": "social_user_v0",
            "password": "password",
            "traits": {"email": "user@canonical.com"},
        },
    )

    res = action.results
    assert res["identity-id"]


def test_scale_up(
    juju: jubilant.Juju,
) -> None:
    target_unit_number = 2

    juju.cli("scale-application", ADMIN_SERVICE_APP, str(target_unit_number))

    juju.wait(
        ready=and_(
            all_active(ADMIN_SERVICE_APP),
            unit_number(ADMIN_SERVICE_APP, target_unit_number),
        ),
        error=any_error(ADMIN_SERVICE_APP),
        timeout=5 * 60,
    )


@pytest.mark.parametrize(
    "integration_name, remote_app_name_fixture",
    [
        (OPENFGA_INTEGRATION_NAME, "openfga_app_name"),
        (KRATOS_INFO_INTEGRATION_NAME, "kratos_app_name"),
        (HYDRA_ENDPOINTS_INTEGRATION_NAME, "hydra_app_name"),
        (INGRESS_INTEGRATION_NAME, "public_traefik_app_name"),
        (CERTIFICATE_TRANSFER_INTEGRATION_NAME, "self_signed_certificates_app_name"),
        (DATABASE_INTEGRATION_NAME, "db_app_name"),
    ],
)
def test_remove_integration(
    juju: jubilant.Juju,
    integration_name: str,
    remote_app_name_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    remote_app_name = request.getfixturevalue(remote_app_name_fixture)
    with remove_integration(juju, remote_app_name, integration_name):
        juju.wait(
            ready=all_blocked(ADMIN_SERVICE_APP),
            error=any_error(ADMIN_SERVICE_APP),
            timeout=5 * 60,
        )
    juju.wait(
        ready=all_active(ADMIN_SERVICE_APP, remote_app_name),
        error=any_error(ADMIN_SERVICE_APP, remote_app_name),
        timeout=10 * 60,
    )


def test_scale_down(
    juju: jubilant.Juju,
) -> None:
    target_unit_num = 1

    juju.cli("scale-application", ADMIN_SERVICE_APP, str(target_unit_num))

    juju.wait(
        ready=and_(
            all_active(ADMIN_SERVICE_APP),
            unit_number(ADMIN_SERVICE_APP, target_unit_num),
        ),
        error=any_error(ADMIN_SERVICE_APP),
        timeout=5 * 60,
    )


@pytest.mark.teardown
def test_remove_application(juju: jubilant.Juju) -> None:
    """Test removing the application."""
    juju.remove_application(ADMIN_SERVICE_APP, destroy_storage=True)
    juju.wait(lambda s: ADMIN_SERVICE_APP not in s.apps, timeout=1000)
