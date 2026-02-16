#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import jubilant
import pytest
from integration.constants import (
    ADMIN_SERVICE_APP,
    ADMIN_SERVICE_IMAGE,
    CERTIFICATE_TRANSFER_INTEGRATION_NAME,
    DATABASE_INTEGRATION_NAME,
    HYDRA_ENDPOINTS_INTEGRATION_NAME,
    INGRESS_INTEGRATION_NAME,
    KRATOS_INFO_INTEGRATION_NAME,
    OPENFGA_INTEGRATION_NAME,
)
from integration.utils import all_active, any_error

logger = logging.getLogger(__name__)


@pytest.mark.skip
@pytest.mark.upgrade
class TestUpgrade:
    admin_ui_app_name = "admin-ui-upgrade"
    hydra_app_name = "hydra-upgrade"
    kratos_app_name = "kratos-upgrade"
    db_app_name = "postgres-upgrade"
    login_ui_app_name = "login-ui-upgrade"
    openfga_app_name = "openfga-upgrade"
    self_signed_certificates_app_name = "self-signed-certificates-upgrade"
    public_traefik_app_name = "traefik-public-upgrade"
    smtp_integrator_app_name = "smtp-integrator-upgrade"

    def integrate_dependencies(self, juju: jubilant.Juju) -> None:
        juju.integrate(f"{self.hydra_app_name}:pg-database", f"{self.db_app_name}:database")
        juju.integrate(f"{self.kratos_app_name}:pg-database", f"{self.db_app_name}:database")
        juju.integrate(
            f"{self.kratos_app_name}:hydra-endpoint-info",
            f"{self.hydra_app_name}:hydra-endpoint-info",
        )
        juju.integrate(
            f"{self.hydra_app_name}:public-ingress", f"{self.public_traefik_app_name}:ingress"
        )
        juju.integrate(
            f"{self.kratos_app_name}:public-ingress", f"{self.public_traefik_app_name}:ingress"
        )
        juju.integrate(
            f"{self.login_ui_app_name}:ingress", f"{self.public_traefik_app_name}:ingress"
        )
        juju.integrate(
            f"{self.login_ui_app_name}:hydra-endpoint-info",
            f"{self.hydra_app_name}:hydra-endpoint-info",
        )
        juju.integrate(
            f"{self.login_ui_app_name}:ui-endpoint-info", f"{self.hydra_app_name}:ui-endpoint-info"
        )
        juju.integrate(
            f"{self.login_ui_app_name}:ui-endpoint-info",
            f"{self.kratos_app_name}:ui-endpoint-info",
        )
        juju.integrate(
            f"{self.login_ui_app_name}:kratos-info", f"{self.kratos_app_name}:kratos-info"
        )
        juju.integrate(
            f"{self.public_traefik_app_name}:certificates",
            f"{self.self_signed_certificates_app_name}:certificates",
        )
        juju.integrate(f"{self.admin_ui_app_name}:{DATABASE_INTEGRATION_NAME}", self.db_app_name)
        juju.integrate(
            f"{self.admin_ui_app_name}:{KRATOS_INFO_INTEGRATION_NAME}",
            f"{self.kratos_app_name}:{KRATOS_INFO_INTEGRATION_NAME}",
        )
        juju.integrate(
            f"{self.admin_ui_app_name}:{HYDRA_ENDPOINTS_INTEGRATION_NAME}",
            f"{self.hydra_app_name}:{HYDRA_ENDPOINTS_INTEGRATION_NAME}",
        )
        juju.integrate(f"{self.admin_ui_app_name}:oauth", f"{self.hydra_app_name}:oauth")
        juju.integrate(
            f"{self.admin_ui_app_name}:{INGRESS_INTEGRATION_NAME}",
            f"{self.public_traefik_app_name}:{INGRESS_INTEGRATION_NAME}",
        )
        juju.integrate(
            f"{self.admin_ui_app_name}:{OPENFGA_INTEGRATION_NAME}", self.openfga_app_name
        )
        juju.integrate(
            f"{self.admin_ui_app_name}:{CERTIFICATE_TRANSFER_INTEGRATION_NAME}",
            self.self_signed_certificates_app_name,
        )
        juju.integrate(self.admin_ui_app_name, f"{self.smtp_integrator_app_name}:smtp")

    def test_deploy_hydra_from_charmhub(self, juju: jubilant.Juju, mail_deployment: None) -> None:
        juju.deploy(
            f"ch:{ADMIN_SERVICE_APP}",
            app=self.admin_ui_app_name,
            channel="latest/edge",
            trust=True,
        )
        juju.deploy(
            "hydra",
            app=self.hydra_app_name,
            channel="latest/stable",
            trust=True,
        )
        juju.deploy(
            "identity-platform-login-ui-operator",
            app=self.login_ui_app_name,
            channel="latest/stable",
            trust=True,
        )
        juju.deploy(
            "kratos",
            app=self.kratos_app_name,
            channel="latest/stable",
            trust=True,
        )
        juju.deploy(
            "postgresql-k8s",
            app=self.db_app_name,
            channel="latest/stable",
            trust=True,
        )
        juju.deploy(
            "openfga",
            app=self.openfga_app_name,
            channel="latest/stable",
            trust=True,
        )
        juju.deploy(
            "self-signed-certificates",
            app=self.self_signed_certificates_app_name,
            channel="latest/stable",
            trust=True,
        )
        juju.deploy(
            "traefik",
            app=self.public_traefik_app_name,
            channel="latest/stable",
            trust=True,
        )
        juju.deploy(
            "smtp-integrator",
            app=self.smtp_integrator_app_name,
            channel="latest/stable",
            trust=True,
        )

        # integrate with dependencies
        self.integrate_dependencies(juju)

        juju.wait(
            ready=all_active(
                self.openfga_app_name,
                self.db_app_name,
                self.smtp_integrator_app_name,
                self.kratos_app_name,
                self.hydra_app_name,
                self.public_traefik_app_name,
                self.self_signed_certificates_app_name,
            ),
            error=any_error(
                self.openfga_app_name,
                self.db_app_name,
                self.smtp_integrator_app_name,
                self.kratos_app_name,
                self.hydra_app_name,
                self.public_traefik_app_name,
                self.self_signed_certificates_app_name,
            ),
            timeout=20 * 60,
        )

        juju.wait(
            ready=all_active(
                self.admin_ui_app_name,
            ),
            error=any_error(
                self.admin_ui_app_name,
            ),
            timeout=5 * 60,
        )

    def test_upgrade(self, juju: jubilant.Juju, local_charm: str) -> None:
        juju.refresh(
            self.admin_ui_app_name,
            path=str(local_charm),
            resources={"oci-image": ADMIN_SERVICE_IMAGE},
        )

        juju.wait(
            ready=all_active(ADMIN_SERVICE_APP),
            error=any_error(ADMIN_SERVICE_APP),
            timeout=5 * 60,
        )
