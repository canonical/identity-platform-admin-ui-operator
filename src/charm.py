#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""A Juju Kubernetes charmed operator for Identity Platform Admin UI."""

import logging
from typing import Any

from charms.certificate_transfer_interface.v0.certificate_transfer import (
    CertificateAvailableEvent,
    CertificateRemovedEvent,
    CertificateTransferRequires,
)
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.hydra.v0.hydra_endpoints import HydraEndpointsRequirer
from charms.hydra.v0.oauth import OAuthInfoChangedEvent, OAuthRequirer
from charms.kratos.v0.kratos_info import KratosInfoRequirer
from charms.loki_k8s.v0.loki_push_api import LogProxyConsumer, PromtailDigestError
from charms.oathkeeper.v0.oathkeeper_info import OathkeeperInfoRequirer
from charms.openfga_k8s.v1.openfga import (
    OpenFGARequires,
    OpenFGAStoreCreateEvent,
    OpenFGAStoreRemovedEvent,
)
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from charms.tempo_k8s.v0.tracing import TracingEndpointRequirer
from charms.traefik_k8s.v2.ingress import (
    IngressPerAppReadyEvent,
    IngressPerAppRequirer,
    IngressPerAppRevokedEvent,
)
from ops.charm import (
    CharmBase,
    ConfigChangedEvent,
    HookEvent,
    RelationChangedEvent,
    UpgradeCharmEvent,
    WorkloadEvent,
)
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus
from ops.pebble import Layer

from configs import CharmConfig
from constants import (
    ADMIN_SERVICE_PORT,
    CERTIFICATE_TRANSFER_INTEGRATION_NAME,
    GRAFANA_DASHBOARD_INTEGRATION_NAME,
    HYDRA_ENDPOINTS_INTEGRATION_NAME,
    INGRESS_INTEGRATION_NAME,
    KRATOS_INFO_INTEGRATION_NAME,
    LOG_DIR,
    LOG_FILE,
    LOKI_API_PUSH_INTEGRATION_NAME,
    OATHKEEPER_INFO_INTEGRATION_NAME,
    OAUTH_INTEGRATION_NAME,
    OPENFGA_INTEGRATION_NAME,
    OPENFGA_STORE_NAME,
    PEER_INTEGRATION_NAME,
    PROMETHEUS_SCRAPE_INTEGRATION_NAME,
    TEMPO_TRACING_INTEGRATION_NAME,
    WORKLOAD_CONTAINER,
)
from exceptions import PebbleError
from integrations import (
    HydraIntegration,
    IngressIntegration,
    KratosIntegration,
    OathkeeperIntegration,
    OAuthIntegration,
    OpenFGAIntegration,
    OpenFGAModelData,
    PeerData,
    TracingIntegration,
    load_oauth_client_config,
)
from services import PebbleService, WorkloadService
from utils import (
    block_when,
    container_not_connected,
    integration_not_exists,
    leader_unit,
    wait_when,
)

logger = logging.getLogger(__name__)


class IdentityPlatformAdminUIOperatorCharm(CharmBase):
    def __init__(self, *args: Any):
        super().__init__(*args)

        self._container = self.unit.get_container(WORKLOAD_CONTAINER)

        self.peer_data = PeerData(self.model)
        self._pebble_service = PebbleService(self.unit)
        self._workload_service = WorkloadService(self.unit)

        self.hydra_endpoints_requirer = HydraEndpointsRequirer(
            self, relation_name=HYDRA_ENDPOINTS_INTEGRATION_NAME
        )
        self.hydra_integration = HydraIntegration(self.hydra_endpoints_requirer)

        self.kratos_info_requirer = KratosInfoRequirer(
            self, relation_name=KRATOS_INFO_INTEGRATION_NAME
        )
        self.kratos_integration = KratosIntegration(self.kratos_info_requirer)

        self.oathkeeper_info_requirer = OathkeeperInfoRequirer(
            self, relation_name=OATHKEEPER_INFO_INTEGRATION_NAME
        )
        self.oathkeeper_integration = OathkeeperIntegration(self.oathkeeper_info_requirer)

        self.openfga_requirer = OpenFGARequires(
            self, store_name=OPENFGA_STORE_NAME, relation_name=OPENFGA_INTEGRATION_NAME
        )
        self.openfga_integration = OpenFGAIntegration(self.openfga_requirer)

        self.ingress_requirer = IngressPerAppRequirer(
            self,
            relation_name=INGRESS_INTEGRATION_NAME,
            port=ADMIN_SERVICE_PORT,
            strip_prefix=True,
            redirect_https=False,
        )
        self.ingress_integration = IngressIntegration(self.ingress_requirer)

        oauth_client_config = load_oauth_client_config(self.ingress_integration.ingress_data.url)
        self.oauth_requirer = OAuthRequirer(self, oauth_client_config, OAUTH_INTEGRATION_NAME)
        self.oauth_integration = OAuthIntegration(self.oauth_requirer)

        self.certificate_transfer_requirer = CertificateTransferRequires(
            self, CERTIFICATE_TRANSFER_INTEGRATION_NAME
        )

        self.tracing = TracingEndpointRequirer(
            self,
            relation_name=TEMPO_TRACING_INTEGRATION_NAME,
        )
        self.tracing_integration = TracingIntegration(self.tracing)

        self.metrics_endpoint = MetricsEndpointProvider(
            self,
            relation_name=PROMETHEUS_SCRAPE_INTEGRATION_NAME,
            jobs=[
                {
                    "metrics_path": "/api/v0/metrics",
                    "static_configs": [
                        {
                            "targets": [f"*:{ADMIN_SERVICE_PORT}"],
                        }
                    ],
                }
            ],
        )
        self.loki_consumer = LogProxyConsumer(
            self,
            log_files=[str(LOG_FILE)],
            relation_name=LOKI_API_PUSH_INTEGRATION_NAME,
            container_name=WORKLOAD_CONTAINER,
        )
        self._grafana_dashboards = GrafanaDashboardProvider(
            self, relation_name=GRAFANA_DASHBOARD_INTEGRATION_NAME
        )

        self.framework.observe(self.on.admin_ui_pebble_ready, self._on_admin_ui_pebble_ready)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
        self.framework.observe(
            self.on.identity_platform_admin_ui_relation_changed, self._on_peer_relation_changed
        )

        self.framework.observe(self.ingress_requirer.on.ready, self._on_ingress_changed)
        self.framework.observe(self.ingress_requirer.on.revoked, self._on_ingress_changed)
        self.framework.observe(
            self.openfga_requirer.on.openfga_store_created,
            self._on_openfga_store_created,
        )
        self.framework.observe(
            self.openfga_requirer.on.openfga_store_removed,
            self._on_openfga_store_removed,
        )
        self.framework.observe(
            self.on[HYDRA_ENDPOINTS_INTEGRATION_NAME].relation_changed,
            self._on_config_changed,
        )
        self.framework.observe(
            self.on[KRATOS_INFO_INTEGRATION_NAME].relation_changed,
            self._on_config_changed,
        )
        self.framework.observe(
            self.on[OATHKEEPER_INFO_INTEGRATION_NAME].relation_changed,
            self._on_config_changed,
        )
        self.framework.observe(
            self.oauth_requirer.on.oauth_info_changed,
            self._on_oauth_info_changed,
        )
        self.framework.observe(
            self.oauth_requirer.on.oauth_info_removed,
            self._on_oauth_info_changed,
        )
        self.framework.observe(
            self.certificate_transfer_requirer.on.certificate_available,
            self._on_certificate_available,
        )
        self.framework.observe(
            self.certificate_transfer_requirer.on.certificate_removed,
            self._on_certificate_removed,
        )

        self.framework.observe(
            self.loki_consumer.on.promtail_digest_error,
            self._promtail_error,
        )

    @wait_when(container_not_connected)
    def _on_certificate_available(self, event: CertificateAvailableEvent) -> None:
        self._workload_service.push_ca_certs(event.ca)
        self._handle_status_update_config(event)

    @wait_when(container_not_connected)
    def _on_certificate_removed(self, event: CertificateRemovedEvent) -> None:
        self._workload_service.remove_ca_certs()
        self._handle_status_update_config(event)

    def _on_admin_ui_pebble_ready(self, event: WorkloadEvent) -> None:
        self._workload_service.open_port()
        self._handle_status_update_config(event)

        version = self._workload_service.version
        self._workload_service.version = version

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        self._handle_status_update_config(event)

    def _on_peer_relation_changed(self, event: RelationChangedEvent) -> None:
        self._handle_status_update_config(event)

    @wait_when(
        container_not_connected,
        integration_not_exists(PEER_INTEGRATION_NAME),
    )
    @leader_unit
    def _on_upgrade_charm(self, event: UpgradeCharmEvent) -> None:
        if not self.openfga_integration.is_store_ready():
            return

        openfga_model_id = self._workload_service.create_openfga_model(
            self.openfga_integration.openfga_integration_data
        )
        self.peer_data[self._workload_service.version] = {"openfga_model_id": openfga_model_id}

    def _on_ingress_changed(
        self, event: IngressPerAppReadyEvent | IngressPerAppRevokedEvent
    ) -> None:
        if self.unit.is_leader():
            ingress_data = self.ingress_integration.ingress_data
            self.oauth_integration.update_oauth_client_config(ingress_url=ingress_data.url)

        self._handle_status_update_config(event)

    def _on_oauth_info_changed(self, event: OAuthInfoChangedEvent) -> None:
        if self.unit.is_leader():
            ingress_data = self.ingress_integration.ingress_data
            self.oauth_integration.update_oauth_client_config(ingress_data.url)

        self._handle_status_update_config(event)

    @wait_when(
        container_not_connected,
        integration_not_exists(PEER_INTEGRATION_NAME),
    )
    def _on_openfga_store_created(self, event: OpenFGAStoreCreateEvent) -> None:
        if not self.openfga_integration.is_store_ready():
            event.defer()
            return

        if self.unit.is_leader():
            openfga_model_id = self._workload_service.create_openfga_model(
                self.openfga_integration.openfga_integration_data
            )
            self.peer_data[self._workload_service.version] = {"openfga_model_id": openfga_model_id}

        self._handle_status_update_config(event)

    def _on_openfga_store_removed(self, event: OpenFGAStoreRemovedEvent) -> None:
        if self.unit.is_leader():
            self.peer_data.pop(key=self._workload_service.version)

        self._handle_status_update_config(event)

    @wait_when(
        container_not_connected,
        integration_not_exists(PEER_INTEGRATION_NAME),
    )
    @block_when(
        integration_not_exists(KRATOS_INFO_INTEGRATION_NAME),
        integration_not_exists(HYDRA_ENDPOINTS_INTEGRATION_NAME),
        integration_not_exists(OPENFGA_INTEGRATION_NAME),
        integration_not_exists(INGRESS_INTEGRATION_NAME),
    )
    def _handle_status_update_config(self, event: HookEvent) -> None:
        if self.oauth_integration.is_ready() and (
            not self.model.relations[CERTIFICATE_TRANSFER_INTEGRATION_NAME]
        ):
            self.unit.status = BlockedStatus(
                "Missing certificate_transfer integration with oauth provider"
            )
            return

        self.unit.status = MaintenanceStatus("Configuring the Admin Service container")

        self._workload_service.prepare_dir(path=LOG_DIR)

        if not self.openfga_integration.is_store_ready():
            event.defer()
            self.unit.status = WaitingStatus("Waiting for OpenFGA store")
            return

        if not self.peer_data[self._workload_service.version]:
            event.defer()
            self.unit.status = WaitingStatus("Waiting for OpenFGA model")
            return

        try:
            self._pebble_service.plan(self._pebble_layer)
        except PebbleError:
            self.unit.status = BlockedStatus("Failed to plan pebble layer, please check the logs")
            return

        self.unit.status = ActiveStatus()

    @property
    def _pebble_layer(self) -> Layer:
        openfga_integration_data = self.openfga_integration.openfga_integration_data
        openfga_model_data = OpenFGAModelData.load(self.peer_data[self._workload_service.version])
        kratos_data = self.kratos_integration.kratos_data
        hydra_data = self.hydra_integration.hydra_data
        ingress_data = self.ingress_integration.ingress_data
        oathkeeper_data = self.oathkeeper_integration.oathkeeper_data
        oauth_data = self.oauth_integration.oauth_provider_data
        tracing_data = self.tracing_integration.tracing_data
        charm_config = CharmConfig(self.config)

        return self._pebble_service.render_pebble_layer(
            kratos_data,
            hydra_data,
            ingress_data,
            oathkeeper_data,
            oauth_data,
            openfga_integration_data,
            openfga_model_data,
            tracing_data,
            charm_config,
        )

    def _promtail_error(self, event: PromtailDigestError) -> None:
        logger.error(event.message)


if __name__ == "__main__":
    main(IdentityPlatformAdminUIOperatorCharm)
