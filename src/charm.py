#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""A Juju Kubernetes charmed operator for Identity Platform Admin UI."""

import json
import logging
import os
import socket
import tempfile
from typing import Dict, Optional
from urllib.parse import urlparse

import requests
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.hydra.v0.hydra_endpoints import (
    HydraEndpointsRelationDataMissingError,
    HydraEndpointsRelationMissingError,
    HydraEndpointsRequirer,
)
from charms.hydra.v0.oauth import ClientConfig, OAuthInfoChangedEvent, OAuthRequirer
from charms.kratos.v0.kratos_info import KratosInfoRelationDataMissingError, KratosInfoRequirer
from charms.loki_k8s.v0.loki_push_api import LogProxyConsumer, PromtailDigestError
from charms.oathkeeper.v0.oathkeeper_info import (
    OathkeeperInfoRelationDataMissingError,
    OathkeeperInfoRequirer,
)
from charms.openfga_k8s.v1.openfga import (
    OpenfgaProviderAppData,
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
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, Relation, WaitingStatus
from ops.pebble import ChangeError, Error, ExecError, Layer

from admin_ui_cli import AdminUICLI, CommandOutputParseExceptionError
from certificate_transfer_integration import CertTransfer
from constants import (
    ADMIN_UI_COMMAND,
    ADMIN_UI_PORT,
    CERTIFICATE_TRANSFER_NAME,
    GRAFANA_DASHBOARD_INTEGRATION_NAME,
    HYDRA_ENDPOINTS_INTEGRATION_NAME,
    INGRESS_INTEGRATION_NAME,
    KRATOS_INFO_INTEGRATION_NAME,
    LOG_DIR,
    LOG_FILE,
    LOKI_API_PUSH_INTEGRATION_NAME,
    OATHKEEPER_INFO_INTEGRATION_NAME,
    OAUTH_CALLBACK_PATH,
    OAUTH_GRANT_TYPES,
    OAUTH_INTEGRATION_NAME,
    OAUTH_SCOPES,
    OPENFGA_INTEGRATION_NAME,
    OPENFGA_STORE_NAME,
    PEER,
    PROMETHEUS_SCRAPE_INTEGRATION_NAME,
    RULES_CONFIGMAP_FILE_NAME,
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
        self.kratos_info = KratosInfoRequirer(self, relation_name=KRATOS_INFO_INTEGRATION_NAME)
        self.oathkeeper_info = OathkeeperInfoRequirer(
            self, relation_name=OATHKEEPER_INFO_INTEGRATION_NAME
        )

        self.ingress = IngressPerAppRequirer(
            self,
            relation_name=INGRESS_INTEGRATION_NAME,
            port=ADMIN_UI_PORT,
            strip_prefix=True,
            redirect_https=False,
        )

        self.openfga = OpenFGARequires(self, OPENFGA_STORE_NAME)

        self._admin_ui_cli = AdminUICLI(self._container)

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

        self.oauth = OAuthRequirer(self, self._oauth_client_config, OAUTH_INTEGRATION_NAME)

        self.cert_transfer = CertTransfer(
            self,
            WORKLOAD_CONTAINER_NAME,
            self._handle_status_update_config,
            CERTIFICATE_TRANSFER_NAME,
        )

        self.framework.observe(self.on.admin_ui_pebble_ready, self._on_admin_ui_pebble_ready)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
        self.framework.observe(
            self.on.identity_platform_admin_ui_relation_changed, self._on_peer_relation_changed
        )

        self.framework.observe(self.ingress.on.ready, self._on_ingress_ready)
        self.framework.observe(self.ingress.on.revoked, self._on_ingress_revoked)

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

        self.framework.observe(self.oauth.on.oauth_info_changed, self._on_oauth_info_changed)
        self.framework.observe(self.oauth.on.oauth_info_removed, self._on_oauth_info_changed)

        self.framework.observe(
            self.openfga.on.openfga_store_created,
            self._on_openfga_store_created,
        )

        self.framework.observe(
            self.openfga.on.openfga_store_removed,
            self._on_openfga_store_removed,
        )

        self.framework.observe(
            self.loki_consumer.on.promtail_digest_error,
            self._promtail_error,
        )

    def _on_admin_ui_pebble_ready(self, event: WorkloadEvent) -> None:
        """Define and start a workload using the Pebble API."""
        self.unit.open_port(protocol="tcp", port=ADMIN_UI_PORT)

        self._handle_status_update_config(event)

        if not self._container.can_connect():
            event.defer()
            logger.info("Cannot connect to admin-ui container. Deferring the event.")
            self.unit.status = WaitingStatus("Waiting to connect to admin-ui container")
            return

        self._set_version()

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        """Handle changed configuration."""
        self._handle_status_update_config(event)

    def _on_peer_relation_changed(self, event: RelationChangedEvent) -> None:
        self._handle_status_update_config(event)

    def _on_ingress_ready(self, event: IngressPerAppReadyEvent) -> None:
        self._handle_status_update_config(event)

    def _on_ingress_revoked(self, event: IngressPerAppRevokedEvent) -> None:
        self._handle_status_update_config(event)

    def _on_oauth_info_changed(self, event: OAuthInfoChangedEvent) -> None:
        self._handle_status_update_config(event)

    def _on_openfga_store_created(self, event: OpenFGAStoreCreateEvent) -> None:
        """Handle openfga store created event."""
        if not self._container.can_connect():
            event.defer()
            logger.info("Cannot connect to admin-ui container. Deferring the event.")
            self.unit.status = WaitingStatus("Waiting to connect to admin-ui container")
            return

        if not self._peers:
            self.unit.status = WaitingStatus("Waiting for peer relation")
            event.defer()
            return

        openfga_info = self._get_openfga_store_info()
        if not openfga_info:
            logger.debug("No openfga store info found, deferring the event")
            event.defer()
            return

        self._create_openfga_model(openfga_info)
        self._handle_status_update_config(event)

    def _on_openfga_store_removed(self, event: OpenFGAStoreRemovedEvent) -> None:
        """Handle openfga store removed event."""
        logger.info("OpenFGA store was removed")
        if self.unit.is_leader():
            self._pop_peer_data(key=self._get_version())

        self._handle_status_update_config(event)

    def _on_upgrade_charm(self, event: UpgradeCharmEvent) -> None:
        """Handle charm upgrade event.

        Create a new model to ensure the migration was run.
        """
        if not self._container.can_connect():
            event.defer()
            logger.info("Cannot connect to admin-ui container. Deferring the event.")
            self.unit.status = WaitingStatus("Waiting to connect to admin-ui container")
            return

        if not self._peers:
            self.unit.status = WaitingStatus("Waiting for peer relation")
            event.defer()
            return

        if openfga_info := self._get_openfga_store_info():
            self._create_openfga_model(openfga_info)

    def _get_openfga_store_info(self) -> Optional[OpenfgaProviderAppData]:
        openfga_info = self.openfga.get_store_info()
        if not openfga_info or not openfga_info.store_id:
            logger.info("No openfga store info available")
            return None

        return openfga_info

    def _handle_status_update_config(self, event: HookEvent) -> None:  # noqa: C901
        if not self._container.can_connect():
            event.defer()
            logger.info("Cannot connect to admin-ui container. Deferring the event.")
            self.unit.status = WaitingStatus("Waiting to connect to admin-ui container")
            return

        if not self._peers:
            self.unit.status = WaitingStatus("Waiting for peer relation")
            event.defer()
            return

        if not self.model.relations[KRATOS_INFO_INTEGRATION_NAME]:
            self.unit.status = BlockedStatus("Missing required relation with kratos")
            return

        if not self.model.relations[HYDRA_ENDPOINTS_INTEGRATION_NAME]:
            self.unit.status = BlockedStatus("Missing required relation with hydra")
            return

        if not self.model.relations[OPENFGA_INTEGRATION_NAME]:
            self.unit.status = BlockedStatus("Missing required relation with openfga")
            return

        if (
            self.model.relations[OAUTH_INTEGRATION_NAME]
            and not self.model.relations[INGRESS_INTEGRATION_NAME]
        ):
            self.unit.status = BlockedStatus("Ingress relation is required for oauth")
            return

        if not self._validate_cert_trust():
            self.unit.status = BlockedStatus(
                "Missing certificate_transfer relation with oauth provider"
            )
            return

        self.unit.status = MaintenanceStatus("Configuring the container")

        self.oauth.update_client_config(client_config=self._oauth_client_config)

        # Make sure the directory for the logfile exists
        if not self._container.isdir(str(LOG_DIR)):
            self._container.make_dir(path=str(LOG_DIR), make_parents=True)
            logger.info(f"Created directory {LOG_DIR}")

        self.cert_transfer.push_ca_certs()

        if not (self._get_openfga_store_info() and self._openfga_model_id):
            logger.info("Openfga store and model unavailable, deferring the event")
            event.defer()
            self.unit.status = WaitingStatus("Waiting for openfga store and model")
            return

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

    def _get_kratos_info(self) -> Dict:
        kratos_info = {}
        if self.kratos_info.is_ready():
            try:
                kratos_info = self.kratos_info.get_kratos_info()
            except KratosInfoRelationDataMissingError:
                logger.info("No kratos-info relation data found")
        return kratos_info

    def _get_oathkeeper_info(self) -> Dict:
        oathkeeper_info = {}
        if self.oathkeeper_info.is_ready():
            try:
                oathkeeper_info = self.oathkeeper_info.get_oathkeeper_info()
            except OathkeeperInfoRelationDataMissingError:
                logger.info("No oathkeeper-info relation data found")
        return oathkeeper_info

    def _promtail_error(self, event: PromtailDigestError) -> None:
        logger.error(event.message)

    def _create_openfga_model(self, openfga_info: OpenfgaProviderAppData) -> None:
        if not self.unit.is_leader():
            logger.debug("Unit does not have leadership")
            return

        try:
            model_id = self._admin_ui_cli.create_openfga_model(openfga_info)
        except ExecError as err:
            logger.error(f"Exited with code: {err.exit_code}. Stderr: {err.stderr}")
            return
        except Error as err:
            logger.error(f"Something went wrong when trying to run the command: {err}")
            return
        except CommandOutputParseExceptionError as e:
            logger.error(f"Failed to get the model id: {e}")
            return

        logger.info(f"Successfully created an openfga model: {model_id}")
        self._set_peer_data(key=self._get_version(), data={"openfga_model_id": model_id})

    def _get_version(self) -> Optional[str]:
        try:
            version = self._admin_ui_cli.get_version()
        except ExecError as err:
            logger.error(f"Exited with code {err.exit_code}. Stderr: {err.stderr}")
            return
        except Error as err:
            logger.error(f"Something went wrong when trying to run the command: {err}")
            return

        return version

    def _set_version(self) -> None:
        if version := self._get_version():
            self.unit.set_workload_version(version)
            logger.info(f"Set workload version: {version}")

    def _set_peer_data(self, key: str, data: Dict) -> None:
        """Put information into the peer data bucket."""
        if not (peers := self._peers):
            return
        peers.data[self.app][key] = json.dumps(data)

    def _get_peer_data(self, key: str) -> Dict:
        """Retrieve information from the peer data bucket."""
        if not (peers := self._peers):
            return {}
        data = peers.data[self.app].get(key, "")
        return json.loads(data) if data else {}

    def _pop_peer_data(self, key: str) -> Dict:
        """Retrieve and remove information from the peer data bucket."""
        if not (peers := self._peers):
            return {}
        data = peers.data[self.app].pop(key, "")
        return json.loads(data) if data else {}

    def _validate_cert_trust(self) -> bool:
        provider_info = self.oauth.get_provider_info()
        if not provider_info:
            return True

        openid_config_url = os.path.join(
            provider_info.issuer_url, ".well-known/openid-configuration"
        )

        with tempfile.NamedTemporaryFile(mode="w+t", delete=False) as f:
            f.write(self.cert_transfer.ca_bundle)
            f.close()
            try:
                requests.get(openid_config_url, verify=f.name)
            except requests.exceptions.SSLError:
                return False
            os.remove(f.name)

        return True

    @property
    def _peers(self) -> Optional[Relation]:
        """Fetch the peer relation."""
        return self.model.get_relation(PEER)

    @property
    def _openfga_model_id(self) -> Optional[str]:
        peer_data = self._get_peer_data(self._get_version())
        return peer_data.get("openfga_model_id", None)

    @property
    def _admin_ui_pebble_layer(self) -> Layer:
        """Define pebble layer."""
        kratos_info = self._get_kratos_info()
        oathkeeper_info = self._get_oathkeeper_info()
        openfga_info = self._get_openfga_store_info()
        openfga_url = urlparse(openfga_info.http_api_url)

        container_env = {
            "AUTHORIZATION_ENABLED": True,
            "OPENFGA_AUTHORIZATION_MODEL_ID": self._openfga_model_id,
            "OPENFGA_STORE_ID": openfga_info.store_id,
            "OPENFGA_API_TOKEN": openfga_info.token,
            "OPENFGA_API_SCHEME": openfga_url.scheme,
            "OPENFGA_API_HOST": openfga_url.netloc,
            "KRATOS_ADMIN_URL": kratos_info.get("admin_endpoint", ""),
            "KRATOS_PUBLIC_URL": kratos_info.get("public_endpoint", ""),
            "HYDRA_ADMIN_URL": self._get_hydra_endpoint_info(),
            "IDP_CONFIGMAP_NAME": kratos_info.get("providers_configmap_name", ""),
            "IDP_CONFIGMAP_NAMESPACE": kratos_info.get("configmaps_namespace", ""),
            "SCHEMAS_CONFIGMAP_NAME": kratos_info.get("schemas_configmap_name", ""),
            "SCHEMAS_CONFIGMAP_NAMESPACE": kratos_info.get("configmaps_namespace", ""),
            "OATHKEEPER_PUBLIC_URL": oathkeeper_info.get("public_endpoint", ""),
            "RULES_CONFIGMAP_NAME": oathkeeper_info.get("rules_configmap_name", ""),
            "RULES_CONFIGMAP_NAMESPACE": oathkeeper_info.get("configmaps_namespace", ""),
            "RULES_CONFIGMAP_FILE_NAME": RULES_CONFIGMAP_FILE_NAME,
            "PORT": str(ADMIN_UI_PORT),
            "BASE_URL": self._domain_url,
            "TRACING_ENABLED": False,
            "LOG_LEVEL": self._log_level,
            "LOG_FILE": str(LOG_FILE),
            "DEBUG": self._log_level == "DEBUG",
            "AUTHENTICATION_ENABLED": False,
        }

        if self.oauth.is_client_created():
            oauth_provider_info = self.oauth.get_provider_info()

            container_env.update({
                "AUTHENTICATION_ENABLED": True,
                "OIDC_ISSUER": oauth_provider_info.issuer_url,
                "OAUTH2_CLIENT_ID": oauth_provider_info.client_id,
                "OAUTH2_CLIENT_SECRET": oauth_provider_info.client_secret,
                "OAUTH2_REDIRECT_URI": self._redirect_uri,
                "OAUTH2_CODEGRANT_SCOPES": OAUTH_SCOPES,
                "ACCESS_TOKEN_VERIFICATION_STRATEGY": "jwks"
                if oauth_provider_info.jwt_access_token
                else "userinfo",
            })

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

    @property
    def _internal_url(self) -> str:
        """Return workload's internal URL. Used for ingress."""
        return f"http://{socket.getfqdn()}:{ADMIN_UI_PORT}"

    @property
    def _domain_url(self) -> str:
        return self.ingress.url if self.ingress.is_ready() else self._internal_url

    @property
    def _redirect_uri(self) -> Optional[str]:
        return os.path.join(self._domain_url, OAUTH_CALLBACK_PATH)

    @property
    def _oauth_client_config(self) -> Optional[ClientConfig]:
        c = ClientConfig(
            redirect_uri=self._redirect_uri,
            scope=OAUTH_SCOPES,
            grant_types=OAUTH_GRANT_TYPES,
        )
        # Bootstrap the client config to have the client_id as an aud.
        # TODO(nsklikas): Remove when the login-ui automatically adds it to the audience
        # https://github.com/canonical/identity-platform-login-ui/issues/244
        if hasattr(self, "oauth"):
            oauth_provider_info = self.oauth.get_provider_info()
            if oauth_provider_info and oauth_provider_info.client_id:
                c.audience = [oauth_provider_info.client_id]
        return c


if __name__ == "__main__":  # pragma: nocover
    main(IdentityPlatformAdminUIOperatorCharm)
