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
from ops import EventBase
from ops.charm import (
    CharmBase,
    CollectStatusEvent,
    ConfigChangedEvent,
    RelationChangedEvent,
    UpgradeCharmEvent,
    WorkloadEvent,
)
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
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
    HydraData,
    IngressData,
    KratosData,
    OathkeeperData,
    OAuthIntegration,
    OpenFGAIntegration,
    OpenFGAModelData,
    PeerData,
    TLSCertificates,
    TracingData,
    load_oauth_client_config,
)
from services import PebbleService, WorkloadService
from utils import (
    EVENT_DEFER_CONDITIONS,
    NOOP_CONDITIONS,
    ca_certificate_exists,
    container_connectivity,
    hydra_integration_exists,
    ingress_integration_exists,
    kratos_integration_exists,
    leader_unit,
    openfga_integration_exists,
    openfga_model_readiness,
    openfga_store_readiness,
    peer_integration_exists,
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

        self.kratos_info_requirer = KratosInfoRequirer(
            self, relation_name=KRATOS_INFO_INTEGRATION_NAME
        )

        self.oathkeeper_info_requirer = OathkeeperInfoRequirer(
            self, relation_name=OATHKEEPER_INFO_INTEGRATION_NAME
        )

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

        oauth_client_config = load_oauth_client_config(IngressData.load(self.ingress_requirer).url)
        self.oauth_requirer = OAuthRequirer(self, oauth_client_config, OAUTH_INTEGRATION_NAME)
        self.oauth_integration = OAuthIntegration(self.oauth_requirer)

        self.certificate_transfer_requirer = CertificateTransferRequires(
            self, CERTIFICATE_TRANSFER_INTEGRATION_NAME
        )

        self.tracing_requirer = TracingEndpointRequirer(
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
        self.framework.observe(self.on.collect_unit_status, self._on_collect_status)

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
            self.on[HYDRA_ENDPOINTS_INTEGRATION_NAME].relation_broken,
            self._on_config_changed,
        )
        self.framework.observe(
            self.on[KRATOS_INFO_INTEGRATION_NAME].relation_changed,
            self._on_config_changed,
        )
        self.framework.observe(
            self.on[KRATOS_INFO_INTEGRATION_NAME].relation_broken,
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
            self._on_certificate_changed,
        )
        self.framework.observe(
            self.certificate_transfer_requirer.on.certificate_removed,
            self._on_certificate_changed,
        )

        self.framework.observe(
            self.loki_consumer.on.promtail_digest_error,
            self._promtail_error,
        )

    def _on_admin_ui_pebble_ready(self, event: WorkloadEvent) -> None:
        self._workload_service.open_port()
        self._holistic_handler(event)

        version = self._workload_service.version
        self._workload_service.version = version

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        self._holistic_handler(event)

    def _on_peer_relation_changed(self, event: RelationChangedEvent) -> None:
        self._holistic_handler(event)

    @leader_unit
    def _on_upgrade_charm(self, event: UpgradeCharmEvent) -> None:
        if (not container_connectivity(self)) or (not peer_integration_exists(self)):
            event.defer()
            return

        if not openfga_store_readiness(self):
            return

        openfga_model_id = self._workload_service.create_openfga_model(
            self.openfga_integration.openfga_integration_data
        )
        self.peer_data[self._workload_service.version] = {"openfga_model_id": openfga_model_id}

    def _on_ingress_changed(
        self, event: IngressPerAppReadyEvent | IngressPerAppRevokedEvent
    ) -> None:
        if self.unit.is_leader():
            ingress_data = IngressData.load(self.ingress_requirer)
            self.oauth_integration.update_oauth_client_config(ingress_url=ingress_data.url)

        self._holistic_handler(event)

    def _on_oauth_info_changed(self, event: OAuthInfoChangedEvent) -> None:
        if self.unit.is_leader():
            ingress_data = IngressData.load(self.ingress_requirer)
            self.oauth_integration.update_oauth_client_config(ingress_data.url)

        self._holistic_handler(event)

    def _on_openfga_store_created(self, event: OpenFGAStoreCreateEvent) -> None:
        if (
            (not container_connectivity(self))
            or (not peer_integration_exists(self))
            or (not openfga_store_readiness(self))
        ):
            event.defer()
            return

        if self.unit.is_leader():
            openfga_model_id = self._workload_service.create_openfga_model(
                self.openfga_integration.openfga_integration_data
            )
            self.peer_data[self._workload_service.version] = {"openfga_model_id": openfga_model_id}

        self._holistic_handler(event)

    def _on_openfga_store_removed(self, event: OpenFGAStoreRemovedEvent) -> None:
        if self.unit.is_leader():
            self.peer_data.pop(key=self._workload_service.version)

        self._holistic_handler(event)

    def _on_certificate_changed(
        self, event: CertificateAvailableEvent | CertificateRemovedEvent
    ) -> None:
        # Delegate to the holistic method for managing TLS certificates in container's filesystem
        self._holistic_handler(event)

    def _on_collect_status(self, event: CollectStatusEvent) -> None:  # noqa: C901
        """The central management of the charm operator's status."""
        if not container_connectivity(self):
            event.add_status(WaitingStatus("Container is not connected yet"))

        if not peer_integration_exists(self):
            event.add_status(WaitingStatus(f"Missing integration {PEER_INTEGRATION_NAME}"))

        if not kratos_integration_exists(self):
            event.add_status(BlockedStatus(f"Missing integration {KRATOS_INFO_INTEGRATION_NAME}"))

        if not hydra_integration_exists(self):
            event.add_status(
                BlockedStatus(f"Missing integration {HYDRA_ENDPOINTS_INTEGRATION_NAME}")
            )

        if not openfga_integration_exists(self):
            event.add_status(BlockedStatus(f"Missing integration {OPENFGA_INTEGRATION_NAME}"))

        if not ingress_integration_exists(self):
            event.add_status(BlockedStatus(f"Missing integration {INGRESS_INTEGRATION_NAME}"))

        if not ca_certificate_exists(self):
            event.add_status(
                BlockedStatus("Missing certificate transfer integration with oauth provider")
            )

        if not openfga_store_readiness(self):
            event.add_status(WaitingStatus("OpenFGA store is not ready yet"))

        if not openfga_model_readiness(self):
            event.add_status(WaitingStatus("OpenFGA model is not ready yet"))

        try:
            self._pebble_service.plan(self._pebble_layer)
        except PebbleError:
            event.add_status(
                BlockedStatus(
                    f"Failed to plan pebble layer, please check the {WORKLOAD_CONTAINER} container logs"
                )
            )

        event.add_status(ActiveStatus())

    def _holistic_handler(self, event: EventBase) -> None:
        if not all(condition(self) for condition in NOOP_CONDITIONS):
            return

        if not all(condition(self) for condition in EVENT_DEFER_CONDITIONS):
            event.defer()
            return

        self._workload_service.prepare_dir(path=LOG_DIR)

        # Install the certificates in various event scenarios
        certs = TLSCertificates.load(self.certificate_transfer_requirer)
        self._workload_service.push_ca_certs(certs.ca_bundle)

    @property
    def _pebble_layer(self) -> Layer:
        openfga_integration_data = self.openfga_integration.openfga_integration_data
        openfga_model_data = OpenFGAModelData.load(self.peer_data[self._workload_service.version])
        kratos_data = KratosData.load(self.kratos_info_requirer)
        hydra_data = HydraData.load(self.hydra_endpoints_requirer)
        ingress_data = IngressData.load(self.ingress_requirer)
        oathkeeper_data = OathkeeperData.load(self.oathkeeper_info_requirer)
        oauth_data = self.oauth_integration.oauth_provider_data
        tracing_data = TracingData.load(self.tracing_requirer)
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
