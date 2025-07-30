#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""A Juju Kubernetes charmed operator for Identity Platform Admin UI."""

import logging
from functools import cached_property
from typing import Any

from charms.certificate_transfer_interface.v1.certificate_transfer import (
    CertificatesAvailableEvent,
    CertificatesRemovedEvent,
    CertificateTransferRequires,
)
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseCreatedEvent,
    DatabaseEndpointsChangedEvent,
    DatabaseRequires,
)
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.hydra.v0.hydra_endpoints import HydraEndpointsRequirer
from charms.hydra.v0.oauth import OAuthInfoChangedEvent, OAuthRequirer
from charms.kratos.v0.kratos_info import KratosInfoRequirer
from charms.loki_k8s.v1.loki_push_api import LogForwarder
from charms.observability_libs.v0.kubernetes_compute_resources_patch import (
    K8sResourcePatchFailedEvent,
    KubernetesComputeResourcesPatch,
    ResourceRequirements,
    adjust_resource_requirements,
)
from charms.openfga_k8s.v1.openfga import (
    OpenFGARequires,
    OpenFGAStoreCreateEvent,
    OpenFGAStoreRemovedEvent,
)
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from charms.smtp_integrator.v0.smtp import SmtpDataAvailableEvent, SmtpRequires
from charms.tempo_k8s.v2.tracing import TracingEndpointRequirer
from charms.traefik_k8s.v2.ingress import (
    IngressPerAppReadyEvent,
    IngressPerAppRequirer,
    IngressPerAppRevokedEvent,
)
from ops import EventBase
from ops.charm import (
    ActionEvent,
    CharmBase,
    CollectStatusEvent,
    ConfigChangedEvent,
    RelationBrokenEvent,
    RelationChangedEvent,
    UpgradeCharmEvent,
    WorkloadEvent,
)
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.pebble import Layer

from cli import CommandLine
from configs import CharmConfig
from constants import (
    ADMIN_SERVICE_PORT,
    CERTIFICATE_TRANSFER_INTEGRATION_NAME,
    DATABASE_INTEGRATION_NAME,
    GRAFANA_DASHBOARD_INTEGRATION_NAME,
    HYDRA_ENDPOINTS_INTEGRATION_NAME,
    INGRESS_INTEGRATION_NAME,
    KRATOS_INFO_INTEGRATION_NAME,
    LOKI_API_PUSH_INTEGRATION_NAME,
    OAUTH_INTEGRATION_NAME,
    OPENFGA_INTEGRATION_NAME,
    OPENFGA_MODEL_ID,
    OPENFGA_STORE_NAME,
    PEER_INTEGRATION_NAME,
    PROMETHEUS_SCRAPE_INTEGRATION_NAME,
    SMTP_INTEGRATION_NAME,
    TEMPO_TRACING_INTEGRATION_NAME,
    WORKLOAD_CONTAINER,
)
from exceptions import MigrationError, PebbleError
from integrations import (
    DatabaseConfig,
    HydraData,
    IngressData,
    KratosData,
    OAuthIntegration,
    OpenFGAIntegration,
    OpenFGAModelData,
    PeerData,
    SmtpProviderData,
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
    database_integration_exists,
    hydra_integration_exists,
    ingress_integration_exists,
    kratos_integration_exists,
    leader_unit,
    migration_needed_on_leader,
    migration_needed_on_non_leader,
    oauth_integration_exists,
    openfga_integration_exists,
    openfga_model_readiness,
    openfga_store_readiness,
    peer_integration_exists,
    smtp_integration_exists,
)

logger = logging.getLogger(__name__)


class IdentityPlatformAdminUIOperatorCharm(CharmBase):
    def __init__(self, *args: Any):
        super().__init__(*args)

        self._container = self.unit.get_container(WORKLOAD_CONTAINER)
        self._cli = CommandLine(self._container)

        self.peer_data = PeerData(self.model)
        self._pebble_service = PebbleService(self.unit)
        self._workload_service = WorkloadService(self.unit)

        self.database_requirer = DatabaseRequires(
            self,
            relation_name=DATABASE_INTEGRATION_NAME,
            database_name=f"{self.model.name}_{self.app.name}",
            extra_user_roles="SUPERUSER",
        )

        self.hydra_endpoints_requirer = HydraEndpointsRequirer(
            self, relation_name=HYDRA_ENDPOINTS_INTEGRATION_NAME
        )

        self.kratos_info_requirer = KratosInfoRequirer(
            self, relation_name=KRATOS_INFO_INTEGRATION_NAME
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
            self,
            CERTIFICATE_TRANSFER_INTEGRATION_NAME,
        )

        self.tracing_requirer = TracingEndpointRequirer(
            self,
            relation_name=TEMPO_TRACING_INTEGRATION_NAME,
            protocols=["otlp_grpc", "otlp_http"],
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
        self._log_forwarder = LogForwarder(self, relation_name=LOKI_API_PUSH_INTEGRATION_NAME)
        self._grafana_dashboards = GrafanaDashboardProvider(
            self, relation_name=GRAFANA_DASHBOARD_INTEGRATION_NAME
        )

        self.smtp_requirer = SmtpRequires(self)

        self.resources_patch = KubernetesComputeResourcesPatch(
            self,
            WORKLOAD_CONTAINER,
            resource_reqs_func=self._resource_reqs_from_config,
        )

        self.framework.observe(self.on.admin_ui_pebble_ready, self._on_admin_ui_pebble_ready)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
        self.framework.observe(
            self.on.identity_platform_admin_ui_relation_changed, self._on_peer_relation_changed
        )
        self.framework.observe(self.on.collect_unit_status, self._on_collect_status)

        # resource patching
        self.framework.observe(
            self.resources_patch.on.patch_failed, self._on_resource_patch_failed
        )

        # database
        self.framework.observe(
            self.database_requirer.on.database_created, self._on_database_created
        )
        self.framework.observe(
            self.database_requirer.on.endpoints_changed, self._on_database_changed
        )
        self.framework.observe(
            self.on[DATABASE_INTEGRATION_NAME].relation_broken,
            self._on_database_integration_broken,
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
            self.oauth_requirer.on.oauth_info_changed,
            self._on_oauth_info_changed,
        )
        self.framework.observe(
            self.oauth_requirer.on.oauth_info_removed,
            self._on_oauth_info_changed,
        )
        self.framework.observe(
            self.certificate_transfer_requirer.on.certificate_set_updated,
            self._on_certificate_changed,
        )
        self.framework.observe(
            self.certificate_transfer_requirer.on.certificates_removed,
            self._on_certificate_changed,
        )
        self.framework.observe(
            self.smtp_requirer.on.smtp_data_available,
            self._on_smtp_data_available,
        )

        # actions
        self.framework.observe(
            self.on.create_identity_action,
            self._on_create_identity_action,
        )
        self.framework.observe(
            self.on.run_migration_up_action,
            self._on_run_migration_up_action,
        )
        self.framework.observe(
            self.on.run_migration_down_action,
            self._on_run_migration_down_action,
        )
        self.framework.observe(
            self.on.run_migration_status_action,
            self._on_run_migration_status_action,
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
        self.peer_data[self._workload_service.version] = {OPENFGA_MODEL_ID: openfga_model_id}

        self._holistic_handler(event)

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
            self.peer_data[self._workload_service.version] = {OPENFGA_MODEL_ID: openfga_model_id}

        self._holistic_handler(event)

    def _on_openfga_store_removed(self, event: OpenFGAStoreRemovedEvent) -> None:
        if self.unit.is_leader():
            self.peer_data.pop(key=self._workload_service.version)

        self._holistic_handler(event)

    def _on_certificate_changed(
        self,
        event: CertificatesAvailableEvent | CertificatesRemovedEvent,
    ) -> None:
        # Delegate to the holistic method for managing TLS certificates in container's filesystem
        self._holistic_handler(event)

    def _on_smtp_data_available(self, event: SmtpDataAvailableEvent) -> None:
        self._holistic_handler(event)

    def _on_resource_patch_failed(self, event: K8sResourcePatchFailedEvent) -> None:
        logger.error(f"Failed to patch resource constraints: {event.message}")
        self.unit.status = BlockedStatus(event.message)

    def _on_database_created(self, event: DatabaseCreatedEvent) -> None:
        self._holistic_handler(event)

    def _on_database_changed(self, event: DatabaseEndpointsChangedEvent) -> None:
        self._holistic_handler(event)

    def _on_database_integration_broken(self, event: RelationBrokenEvent) -> None:
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

        if not oauth_integration_exists(self):
            event.add_status(BlockedStatus(f"Missing integration {OAUTH_INTEGRATION_NAME}"))

        if not openfga_integration_exists(self):
            event.add_status(BlockedStatus(f"Missing integration {OPENFGA_INTEGRATION_NAME}"))

        if not ingress_integration_exists(self):
            event.add_status(BlockedStatus(f"Missing integration {INGRESS_INTEGRATION_NAME}"))

        if not ca_certificate_exists(self):
            event.add_status(
                BlockedStatus("Missing certificate transfer integration with oauth provider")
            )

        if not smtp_integration_exists(self):
            event.add_status(BlockedStatus(f"Missing integration {SMTP_INTEGRATION_NAME}"))

        if not database_integration_exists(self):
            event.add_status(BlockedStatus(f"Missing integration {DATABASE_INTEGRATION_NAME}"))

        if migration_needed_on_leader(self):
            event.add_status(
                BlockedStatus(
                    "Either Database migration is required, or the migration job has failed. Please check juju logs"
                )
            )

        if migration_needed_on_non_leader(self):
            event.add_status(WaitingStatus("Waiting for leader unit to run the migration"))

        if not openfga_store_readiness(self):
            event.add_status(WaitingStatus("OpenFGA store is not ready yet"))

        if not openfga_model_readiness(self):
            event.add_status(
                WaitingStatus(
                    "OpenFGA model is not ready yet. If this persists, check `juju logs` for errors"
                )
            )

        event.add_status(ActiveStatus())

    def _holistic_handler(self, event: EventBase) -> None:
        if not all(condition(self) for condition in NOOP_CONDITIONS):
            return

        if not all(condition(self) for condition in EVENT_DEFER_CONDITIONS):
            event.defer()
            return

        if self.unit.is_leader():
            self.peer_data.prepare()

        # Install the certificates in various event scenarios
        self._workload_service.push_ca_certs(self._ca_bundle)

        if self.migration_needed:
            if not self.unit.is_leader():
                logger.info(
                    "Unit does not have leadership. Wait for leader unit to run the migration."
                )
                event.defer()
                return

            database_config = DatabaseConfig.load(self.database_requirer)
            try:
                self._cli.migrate_up(dsn=database_config.dsn)
            except MigrationError:
                logger.error("Auto migration job failed. Please use the run-migration-up action")
                return

            migration_version = database_config.migration_version
            self.peer_data[migration_version] = self._workload_service.version

        try:
            self._pebble_service.plan(self._pebble_layer)
        except PebbleError:
            logger.error(
                f"Failed to plan pebble layer, please check the {WORKLOAD_CONTAINER} container logs"
            )
            raise

    @cached_property
    def _ca_bundle(self) -> str:
        return TLSCertificates.load(self.certificate_transfer_requirer).ca_bundle

    @property
    def migration_needed(self) -> bool:
        if not peer_integration_exists(self):
            return False

        database_config = DatabaseConfig.load(self.database_requirer)
        return self.peer_data[database_config.migration_version] != self._workload_service.version

    @property
    def _pebble_layer(self) -> Layer:
        database_config = DatabaseConfig.load(self.database_requirer)
        openfga_integration_data = self.openfga_integration.openfga_integration_data
        openfga_model_data = OpenFGAModelData.load(self.peer_data[self._workload_service.version])  # type: ignore[arg-type]
        kratos_data = KratosData.load(self.kratos_info_requirer)
        hydra_data = HydraData.load(self.hydra_endpoints_requirer)
        ingress_data = IngressData.load(self.ingress_requirer)
        oauth_data = self.oauth_integration.oauth_provider_data
        tracing_data = TracingData.load(self.tracing_requirer)
        smtp_data = SmtpProviderData.load(self.smtp_requirer)
        charm_config = CharmConfig(self.config)

        return self._pebble_service.render_pebble_layer(
            database_config,
            kratos_data,
            hydra_data,
            ingress_data,
            oauth_data,
            openfga_integration_data,
            openfga_model_data,
            tracing_data,
            smtp_data,
            self.peer_data,
            charm_config,
        )

    def _on_create_identity_action(self, event: ActionEvent) -> None:
        traits = event.params["traits"]
        schema_id = event.params["schema"]
        password = event.params["password"]

        if not (res := self._cli.create_identity(traits, schema_id=schema_id, password=password)):
            event.fail("Failed to create the identity. Please check `juju logs`")
            return

        event.log(f"Successfully created the identity: {res}")
        event.set_results({"identity-id": res})

    def _on_run_migration_up_action(self, event: ActionEvent) -> None:
        if not self.unit.is_leader():
            event.fail("Non-leader unit cannot run migration action")
            return

        if not self._workload_service.is_running:
            event.fail("Service is not ready. Please re-run the action when the charm is active")
            return

        if not peer_integration_exists(self):
            event.fail("Peer integration is not ready yet")
            return

        event.log("Start migrating up the database")

        database_config = DatabaseConfig.load(self.database_requirer)
        timeout = float(event.params.get("timeout", 120))
        try:
            self._cli.migrate_up(dsn=database_config.dsn, timeout=timeout)
        except MigrationError as err:
            event.fail(f"Database migration up failed: {err}")
            return
        else:
            event.log("Successfully migrated up the database")

        migration_version = database_config.migration_version
        self.peer_data[migration_version] = self._workload_service.version
        event.log("Successfully updated migration version")

        self._holistic_handler(event)

    def _on_run_migration_down_action(self, event: ActionEvent) -> None:
        if not self.unit.is_leader():
            event.fail("Non-leader unit cannot run migration action")
            return

        if not self._workload_service.is_running:
            event.fail("Service is not ready. Please re-run the action when the charm is active")
            return

        if not peer_integration_exists(self):
            event.fail("Peer integration is not ready yet")
            return

        event.log("Start migrating down the database")

        database_config = DatabaseConfig.load(self.database_requirer)
        timeout = float(event.params.get("timeout", 120))
        version = event.params.get("version")
        try:
            self._cli.migrate_down(
                dsn=database_config.dsn,
                version=version,
                timeout=timeout,
            )
        except MigrationError as err:
            event.fail(f"Database migration down failed: {err}")
            return
        else:
            event.log("Successfully migrated down the database")

        migration_version = database_config.migration_version
        self.peer_data[migration_version] = self._workload_service.version
        event.log("Successfully updated migration version")

        self._holistic_handler(event)

    def _on_run_migration_status_action(self, event: ActionEvent) -> None:
        if not self._workload_service.is_running:
            event.fail("Service is not ready. Please re-run the action when the charm is active")
            return

        if not (
            status := self._cli.migrate_status(dsn=DatabaseConfig.load(self.database_requirer).dsn)
        ):
            event.fail("Failed to fetch the status of all database migrations")
            return

        event.log("Successfully fetch the status of all database migrations")
        event.set_results({"status": status})

    def _resource_reqs_from_config(self) -> ResourceRequirements:
        limits = {"cpu": self.model.config.get("cpu"), "memory": self.model.config.get("memory")}
        requests = {"cpu": "100m", "memory": "200Mi"}
        return adjust_resource_requirements(limits, requests, adhere_to_requests=True)


if __name__ == "__main__":
    main(IdentityPlatformAdminUIOperatorCharm)
