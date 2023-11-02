#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Juju charmed operator for the Identity Platform Admin UI."""
import logging
import re
from typing import Optional

from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.loki_k8s.v0.loki_push_api import LogProxyConsumer, PromtailDigestError
from charms.observability_libs.v0.kubernetes_service_patch import KubernetesServicePatch
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
    GRAFANA_DASHBOARD_INTEGRATION_NAME,
    LOG_DIR,
    LOG_FILE,
    LOKI_API_PUSH_INTEGRATION_NAME,
    PROMETHEUS_SCRAPE_INTEGRATION_NAME,
    SERVICE_NAME,
    TEMPO_TRACING_INTEGRATION_NAME,
)

logger = logging.getLogger(__name__)


class IdentityPlatformAdminUiOperatorCharm(CharmBase):
    """Identity Platform Admin Ui charm class."""

    def __init__(self, *args):
        """Initialize Charm."""
        super().__init__(*args)
        self._container = self.unit.get_container(SERVICE_NAME)

        # Initialize Utility Relations
        self.service_patcher = KubernetesServicePatch(
            self, [("identity-platform-admin-ui", int(self._port))]
        )

        self.ingress = IngressPerAppRequirer(
            self,
            relation_name="ingress",
            port=int(self._port),
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
                            "targets": [f"*:{self._port}"],
                        }
                    ],
                }
            ],
        )

        self.loki_consumer = LogProxyConsumer(
            self,
            log_files=[str(LOG_FILE)],
            relation_name=LOKI_API_PUSH_INTEGRATION_NAME,
            container_name=SERVICE_NAME,
        )

        self._grafana_dashboards = GrafanaDashboardProvider(
            self, relation_name=GRAFANA_DASHBOARD_INTEGRATION_NAME
        )

        # TODO: Initialize Identity Platform Relations

        # Register Charm Event Handlers
        self.framework.observe(self.on.admin_ui_pebble_ready, self._on_admin_ui_pebble_ready)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.install, self._on_install)

        # Register Utility Relation Event Handlers
        self.framework.observe(self.ingress.on.ready, self._on_ingress_ready)
        self.framework.observe(self.ingress.on.revoked, self._on_ingress_revoked)
        self.framework.observe(
            self.loki_consumer.on.promtail_digest_error,
            self._promtail_error,
        )

        # TODO: Register Identity Platform Event Handlers

    # Event Handlers
    # Charm event handlers"""

    def _on_admin_ui_pebble_ready(self, event: WorkloadEvent) -> None:
        """Define and start a workload using the Pebble API."""
        if not self._container.can_connect():
            event.defer()
            self.unit.status = WaitingStatus("Waiting to connect to admin-ui container")
            return

        # Makes sure the directory for the logfile exists
        if not self._container.isdir(str(LOG_DIR)):
            self._container.make_dir(path=str(LOG_DIR), make_parents=True)
            logger.info(f"Created directory {LOG_DIR}")

        self._set_version()
        self._update_pebble_layer(event)

    def _on_install(self, event: InstallEvent) -> None:
        if not self._container.can_connect():
            event.defer()
            logger.info("Cannot connect to admin-ui container. Deferring the event.")
            self.unit.status = WaitingStatus("Waiting to connect to admin-ui container")
            return

        # Makes sure the directory for the logfile exists
        # Duplicated to avoid race condition between install and pebble_ready events.
        if not self._container.isdir(LOG_DIR):
            self._container.make_dir(path=LOG_DIR, make_parents=True)
            logger.info(f"Created directory {LOG_DIR}")

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        """Handle changed configuration."""
        self._update_pebble_layer(event)

    def _update_pebble_layer(self, event: HookEvent) -> None:
        if not self._container.can_connect():
            event.defer()
            logger.info("Cannot connect to admin-ui container. Deferring the event.")
            self.unit.status = WaitingStatus("Waiting to connect to admin-ui container")
            return

        self.unit.status = MaintenanceStatus("Configuration in progress")

        self._container.add_layer(SERVICE_NAME, self._admin_ui_pebble_layer, combine=True)
        logger.info("Pebble plan updated with new configuration, replanning")
        try:
            self._container.replan()
        except ChangeError as err:
            logger.error(str(err))
            self.unit.status = BlockedStatus("Failed to replan, please consult the logs")
            return

        self.unit.status = ActiveStatus()

    # Relation event handlers
    # TODO: Identity Platform relation handlers
    # Utility charm relation handlers

    def _on_ingress_ready(self, event: IngressPerAppReadyEvent) -> None:
        if self.unit.is_leader():
            logger.info("This app's public ingress URL: %s", event.url)
        self._update_pebble_layer(event)

    def _on_ingress_revoked(self, event: IngressPerAppRevokedEvent) -> None:
        if self.unit.is_leader():
            logger.info("This app no longer has ingress")
        self._update_pebble_layer(event)

    def _promtail_error(self, event: PromtailDigestError) -> None:
        logger.error(event.message)

    # Utility Methods

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

    # Properties

    @property
    def _admin_ui_pebble_layer(self) -> Layer:
        """Define container configuration."""
        container = {
            "override": "replace",
            "summary": "identity platform admin ui",
            "command": ADMIN_UI_COMMAND,
            "startup": "enabled",
            "environment": {
                "KRATOS_PUBLIC_URL": self._kratos_public_url,
                "KRATOS_ADMIN_URL": self._kratos_admin_url,
                "HYDRA_ADMIN_URL": self._hydra_admin_url,
                "IDP_CONFIGMAP_NAME": self._idp_configmap_name,
                "IDP_CONFIGMAP_NAMESPACE": self._idp_configmap_namespace,
                "SCHEMAS_CONFIGMAP_NAME": self._schemas_configmap_name,
                "SCHEMAS_CONFIGMAP_NAMESPACE": self._schemas_configmap_namespace,
                "PORT": self._port,
                "TRACING_ENABLED": False,
                "LOG_LEVEL": self._log_level,
                "LOG_FILE": str(LOG_FILE),
                "DEBUG": self._log_level == "DEBUG",
            },
        }

        if self._tracing_ready:
            container["environment"]["OTEL_HTTP_ENDPOINT"] = self._tracing_endpoint_info_http
            container["environment"]["OTEL_GRPC_ENDPOINT"] = self._tracing_endpoint_info_grpc
            container["environment"]["TRACING_ENABLED"] = True

        # Define Pebble layer configuration
        pebble_layer = {
            "summary": "Pebble Layer for Identity Platform Admin UI",
            "description": "Pebble Layer for Identity Platform Admin UI",
            "services": {SERVICE_NAME: container},
            "checks": {
                "alive": {
                    "override": "replace",
                    "http": {"url": f"http://localhost:{self._port}/api/v0/status"},
                },
            },
        }
        return Layer(pebble_layer)

    @property
    def _tracing_ready(self) -> bool:
        return self.tracing.is_ready()

    @property
    def _tracing_endpoint_info_http(self) -> str:
        if not self._tracing_ready:
            return ""

        return self.tracing.otlp_http_endpoint() or ""

    @property
    def _tracing_endpoint_info_grpc(self) -> str:
        if not self._tracing_ready:
            return ""

        return self.tracing.otlp_grpc_endpoint() or ""

    """Config Properties"""
    """TODO: phase out for relations"""

    @property
    def _log_level(self) -> str:
        return self.config["log_level"]

    @property
    def _port(self) -> str:
        return self.config["port"]

    @property
    def _kratos_public_url(self) -> str:
        return self.config["kratos_public_url"]

    @property
    def _kratos_admin_url(self) -> str:
        return self.config["kratos_admin_url"]

    @property
    def _hydra_admin_url(self) -> str:
        return self.config["hydra_admin_url"]

    @property
    def _idp_configmap_name(self) -> str:
        return self.config["idp_configmap_name"]

    @property
    def _idp_configmap_namespace(self) -> str:
        return self.config["idp_configmap_namespace"]

    @property
    def _schemas_configmap_name(self) -> str:
        return self.config["schemas_configmap_name"]

    @property
    def _schemas_configmap_namespace(self) -> str:
        return self.config["schemas_configmap_namespace"]


if __name__ == "__main__":  # pragma: nocover
    main(IdentityPlatformAdminUiOperatorCharm)
