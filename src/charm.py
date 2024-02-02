#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""A Juju Kubernetes charmed operator for Identity Platform Admin UI."""
import logging
import re
from typing import Optional

from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.hydra.v0.hydra_endpoints import (
    HydraEndpointsRelationDataMissingError,
    HydraEndpointsRelationMissingError,
    HydraEndpointsRequirer,
)
from charms.kratos.v0.kratos_endpoints import (
    KratosEndpointsRelationDataMissingError,
    KratosEndpointsRequirer,
)
from charms.loki_k8s.v0.loki_push_api import LogProxyConsumer, PromtailDigestError
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from charms.tempo_k8s.v0.tracing import TracingEndpointRequirer
from charms.traefik_k8s.v2.ingress import (
    IngressPerAppReadyEvent,
    IngressPerAppRequirer,
    IngressPerAppRevokedEvent,
)
from ops.charm import CharmBase, ConfigChangedEvent, HookEvent, InstallEvent, WorkloadEvent
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus
from ops.pebble import ChangeError, Error, Layer

from constants import (
    ADMIN_UI_COMMAND,
    ADMIN_UI_PORT,
    GRAFANA_DASHBOARD_INTEGRATION_NAME,
    HYDRA_ENDPOINTS_INTEGRATION_NAME,
    KRATOS_ENDPOINTS_INTEGRATION_NAME,
    LOG_DIR,
    LOG_FILE,
    LOKI_API_PUSH_INTEGRATION_NAME,
    PROMETHEUS_SCRAPE_INTEGRATION_NAME,
    TEMPO_TRACING_INTEGRATION_NAME,
    WORKLOAD_CONTAINER_NAME,
    WORKLOAD_SERVICE_NAME,
)

logger = logging.getLogger(__name__)


class IdentityPlatformAdminUIOperatorCharm(CharmBase):
    """Charm the Identity Platform Admin UI service."""

    def __init__(self, *args):
        """Charm the service."""
        super().__init__(*args)
        self._container = self.unit.get_container(WORKLOAD_CONTAINER_NAME)

        self.hydra_endpoints = HydraEndpointsRequirer(
            self, relation_name=HYDRA_ENDPOINTS_INTEGRATION_NAME
        )
        self.kratos_endpoints = KratosEndpointsRequirer(
            self, relation_name=KRATOS_ENDPOINTS_INTEGRATION_NAME
        )

        self.ingress = IngressPerAppRequirer(
            self,
            relation_name="ingress",
            port=ADMIN_UI_PORT,
            strip_prefix=True,
            redirect_https=False,
        )

        self.tracing = TracingEndpointRequirer(
            self,
            relation_name=TEMPO_TRACING_INTEGRATION_NAME,
        )

        self.metrics_endpoint = MetricsEndpointProvider(
            self,
            relation_name=PROMETHEUS_SCRAPE_INTEGRATION_NAME,
            jobs=[
                {
                    "metrics_path": "/api/v0/metrics",
                    "static_configs": [
                        {
                            "targets": [f"*:{ADMIN_UI_PORT}"],
                        }
                    ],
                }
            ],
        )

        self.loki_consumer = LogProxyConsumer(
            self,
            log_files=[str(LOG_FILE)],
            relation_name=LOKI_API_PUSH_INTEGRATION_NAME,
            container_name=WORKLOAD_CONTAINER_NAME,
        )

        self._grafana_dashboards = GrafanaDashboardProvider(
            self, relation_name=GRAFANA_DASHBOARD_INTEGRATION_NAME
        )

        self.framework.observe(self.on.admin_ui_pebble_ready, self._on_admin_ui_pebble_ready)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.install, self._on_install)

        self.framework.observe(self.ingress.on.ready, self._on_ingress_ready)
        self.framework.observe(self.ingress.on.revoked, self._on_ingress_revoked)

        self.framework.observe(
            self.on[HYDRA_ENDPOINTS_INTEGRATION_NAME].relation_changed,
            self._on_config_changed,
        )

        self.framework.observe(
            self.on[KRATOS_ENDPOINTS_INTEGRATION_NAME].relation_changed,
            self._on_config_changed,
        )

        self.framework.observe(
            self.loki_consumer.on.promtail_digest_error,
            self._promtail_error,
        )

    def _on_install(self, event: InstallEvent) -> None:
        if not self._container.can_connect():
            event.defer()
            logger.info("Cannot connect to admin-ui container. Deferring the event.")
            self.unit.status = WaitingStatus("Waiting to connect to admin-ui container")
            return

        # Make sure the directory for the logfile exists
        # Duplicated to avoid race condition between install and pebble_ready events.
        if not self._container.isdir(LOG_DIR):
            self._container.make_dir(path=LOG_DIR, make_parents=True)
            logger.info(f"Created directory {LOG_DIR}")

    def _on_admin_ui_pebble_ready(self, event: WorkloadEvent) -> None:
        """Define and start a workload using the Pebble API."""
        self.unit.open_port(protocol="tcp", port=ADMIN_UI_PORT)

        if not self._container.can_connect():
            event.defer()
            logger.info("Cannot connect to admin-ui container. Deferring the event.")
            self.unit.status = WaitingStatus("Waiting to connect to admin-ui container")
            return

        # Make sure the directory for the logfile exists
        if not self._container.isdir(str(LOG_DIR)):
            self._container.make_dir(path=str(LOG_DIR), make_parents=True)
            logger.info(f"Created directory {LOG_DIR}")

        self._set_version()
        self._update_pebble_layer(event)

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        """Handle changed configuration."""
        self._update_pebble_layer(event)

    def _on_ingress_ready(self, event: IngressPerAppReadyEvent) -> None:
        if self.unit.is_leader():
            logger.info("This app's public ingress URL: %s", event.url)

    def _on_ingress_revoked(self, event: IngressPerAppRevokedEvent) -> None:
        if self.unit.is_leader():
            logger.info("This app no longer has ingress")

    def _update_pebble_layer(self, event: HookEvent) -> None:
        if not self._container.can_connect():
            event.defer()
            logger.info("Cannot connect to admin-ui container. Deferring the event.")
            self.unit.status = WaitingStatus("Waiting to connect to admin-ui container")
            return

        self.unit.status = MaintenanceStatus("Configuring the container")

        self._container.add_layer(
            WORKLOAD_CONTAINER_NAME, self._admin_ui_pebble_layer, combine=True
        )
        logger.info("Pebble plan updated with new configuration, replanning")

        try:
            self._container.replan()
        except ChangeError as err:
            logger.error(str(err))
            self.unit.status = BlockedStatus("Failed to replan, please consult the logs")
            return

        self.unit.status = ActiveStatus()

    def _get_hydra_endpoint_info(self) -> str:
        hydra_url = ""
        if self.model.relations[HYDRA_ENDPOINTS_INTEGRATION_NAME]:
            try:
                hydra_endpoints = self.hydra_endpoints.get_hydra_endpoints()
                hydra_url = hydra_endpoints["admin_endpoint"]
            except HydraEndpointsRelationMissingError:
                logger.info("No hydra-endpoint-info relation found")
            except HydraEndpointsRelationDataMissingError:
                logger.info("No hydra-endpoint-info relation data found")
        return hydra_url

    def _get_kratos_endpoint_info(self, endpoint_type: str) -> str:
        kratos_url = ""
        if self.model.relations[KRATOS_ENDPOINTS_INTEGRATION_NAME]:
            try:
                kratos_endpoints = self.kratos_endpoints.get_kratos_endpoints()
                kratos_url = kratos_endpoints[endpoint_type]
            except KratosEndpointsRelationDataMissingError:
                logger.info("No kratos-endpoint-info relation data found")
        return kratos_url

    def _promtail_error(self, event: PromtailDigestError) -> None:
        logger.error(event.message)

    def _get_version(self) -> Optional[str]:
        cmd = ["identity-platform-admin-ui", "--version"]
        try:
            process = self._container.exec(cmd)
            stdout, _ = process.wait_output()
        except Error:
            return

        out_re = r"App Version:\s*(.+)\s*$"
        versions = re.search(out_re, stdout)
        if versions:
            return versions[1]

    def _set_version(self) -> None:
        if version := self._get_version():
            self.unit.set_workload_version(version)

    @property
    def _admin_ui_pebble_layer(self) -> Layer:
        """Define pebble layer."""
        container_env = {
            "KRATOS_ADMIN_URL": self._get_kratos_endpoint_info("admin_endpoint"),
            "KRATOS_PUBLIC_URL": self._get_kratos_endpoint_info("public_endpoint"),
            "HYDRA_ADMIN_URL": self._get_hydra_endpoint_info(),
            "IDP_CONFIGMAP_NAME": "providers",
            "IDP_CONFIGMAP_NAMESPACE": self.model.name,
            "SCHEMAS_CONFIGMAP_NAME": "identity-schemas",
            "SCHEMAS_CONFIGMAP_NAMESPACE": self.model.name,
            "OATHKEEPER_PUBLIC_URL": "",
            "RULES_CONFIGMAP_NAME": "access-rules",
            "RULES_CONFIGMAP_NAMESPACE": self.model.name,
            "RULES_CONFIGMAP_FILE_NAME": "admin_ui_rules.json",
            "PORT": str(ADMIN_UI_PORT),
            "TRACING_ENABLED": False,
            "LOG_LEVEL": self._log_level,
            "LOG_FILE": str(LOG_FILE),
            "DEBUG": self._log_level == "DEBUG",
        }

        if self._tracing_ready:
            container_env["TRACING_ENABLED"] = True
            container_env["OTEL_HTTP_ENDPOINT"] = self._tracing_endpoint_info_http
            container_env["OTEL_GRPC_ENDPOINT"] = self._tracing_endpoint_info_grpc

        pebble_layer = {
            "summary": "Pebble Layer for Identity Platform Admin UI",
            "description": "Pebble Layer for Identity Platform Admin UI",
            "services": {
                WORKLOAD_SERVICE_NAME: {
                    "override": "replace",
                    "summary": "identity platform admin ui",
                    "command": ADMIN_UI_COMMAND,
                    "startup": "enabled",
                    "environment": container_env,
                }
            },
            "checks": {
                "alive": {
                    "override": "replace",
                    "http": {"url": f"http://localhost:{ADMIN_UI_PORT}/api/v0/status"},
                },
            },
        }
        return Layer(pebble_layer)

    @property
    def _tracing_ready(self) -> bool:
        return self.tracing.is_ready()

    @property
    def _tracing_endpoint_info_http(self) -> str:
        return self.tracing.otlp_http_endpoint() if self._tracing_ready else ""

    @property
    def _tracing_endpoint_info_grpc(self) -> str:
        return self.tracing.otlp_grpc_endpoint() if self._tracing_ready else ""

    @property
    def _log_level(self) -> str:
        return self.config["log_level"]


if __name__ == "__main__":  # pragma: nocover
    main(IdentityPlatformAdminUIOperatorCharm)
