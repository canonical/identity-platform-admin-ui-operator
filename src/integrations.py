# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
import secrets
import socket
from dataclasses import dataclass
from os.path import join
from typing import Any, Mapping, Optional, Union
from urllib.parse import urlparse

from charms.certificate_transfer_interface.v1.certificate_transfer import (
    CertificateTransferRequires,
)
from charms.hydra.v0.hydra_endpoints import HydraEndpointsRequirer
from charms.hydra.v0.oauth import ClientConfig, OAuthRequirer
from charms.kratos.v0.kratos_info import KratosInfoRequirer
from charms.oathkeeper.v0.oathkeeper_info import OathkeeperInfoRequirer
from charms.openfga_k8s.v1.openfga import OpenFGARequires
from charms.tempo_k8s.v0.tracing import TracingEndpointRequirer
from charms.traefik_k8s.v2.ingress import IngressPerAppRequirer
from ops.model import Model

from constants import (
    ADMIN_SERVICE_PORT,
    CERTIFICATE_TRANSFER_INTEGRATION_NAME,
    COOKIES_KEY,
    DEFAULT_ACCESS_TOKEN_VERIFICATION_STRATEGY,
    OAUTH_CALLBACK_PATH,
    OAUTH_GRANT_TYPES,
    OAUTH_SCOPES,
    PEER_INTEGRATION_NAME,
)
from env_vars import EnvVars
from exceptions import MissingCookieKey

logger = logging.getLogger(__name__)


class PeerData:
    def __init__(self, model: Model) -> None:
        self._model = model
        self._app = model.app

    def __getitem__(self, key: str) -> Union[dict, str]:
        if not (peers := self._model.get_relation(PEER_INTEGRATION_NAME)):
            return {}

        value = peers.data[self._app].get(key)
        return json.loads(value) if value else {}

    def __setitem__(self, key: str, value: Any) -> None:
        if not (peers := self._model.get_relation(PEER_INTEGRATION_NAME)):
            return

        peers.data[self._app][key] = json.dumps(value)

    def pop(self, key: str) -> Union[dict, str]:
        if not (peers := self._model.get_relation(PEER_INTEGRATION_NAME)):
            return {}

        data = peers.data[self._app].pop(key, None)
        return json.loads(data) if data else {}

    def prepare(self) -> None:
        if not self._model.unit.is_leader():
            return

        if not self[COOKIES_KEY]:
            self[COOKIES_KEY] = secrets.token_hex(16)

    def to_env_vars(self) -> EnvVars:
        key = self[COOKIES_KEY]
        if not isinstance(key, str):
            logger.error("No cookie key found in the databag.")
            raise MissingCookieKey()

        return {
            "OAUTH2_AUTH_COOKIES_ENCRYPTION_KEY": key,
        }


@dataclass(frozen=True)
class OpenFGAModelData:
    """The data source of the OpenFGA model."""

    model_id: str = ""

    def to_env_vars(self) -> EnvVars:
        return {
            "OPENFGA_AUTHORIZATION_MODEL_ID": self.model_id,
        }

    @classmethod
    def load(cls, source: Mapping[str, Any]) -> "OpenFGAModelData":
        return OpenFGAModelData(
            model_id=source.get("openfga_model_id", ""),
        )


@dataclass(frozen=True)
class OpenFGAIntegrationData:
    """The data source from the OpenFGA integration."""

    url: str = ""
    api_token: str = ""
    store_id: str = ""

    @property
    def api_scheme(self) -> str:
        return urlparse(self.url).scheme

    @property
    def api_host(self) -> str:
        return urlparse(self.url).netloc

    def to_env_vars(self) -> EnvVars:
        return {
            "OPENFGA_STORE_ID": self.store_id,
            "OPENFGA_API_TOKEN": self.api_token,
            "OPENFGA_API_SCHEME": self.api_scheme,
            "OPENFGA_API_HOST": self.api_host,
        }


class OpenFGAIntegration:
    def __init__(self, integration_requirer: OpenFGARequires) -> None:
        self._openfga_requirer = integration_requirer

    def is_store_ready(self) -> bool:
        provider_data = self._openfga_requirer.get_store_info()
        return provider_data is not None and provider_data.store_id is not None

    @property
    def openfga_integration_data(self) -> OpenFGAIntegrationData:
        if not (provider_data := self._openfga_requirer.get_store_info()):
            return OpenFGAIntegrationData()

        return OpenFGAIntegrationData(
            url=provider_data.http_api_url,  # type: ignore[arg-type]
            api_token=provider_data.token,  # type: ignore[arg-type]
            store_id=provider_data.store_id,  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class KratosData:
    """The data source from the kratos-info integration."""

    admin_url: str = ""
    public_url: str = ""
    idp_configmap_name: str = ""
    idp_configmap_namespace: str = ""
    schemas_configmap_name: str = ""
    schemas_configmap_namespace: str = ""

    def to_env_vars(self) -> EnvVars:
        return {
            "KRATOS_ADMIN_URL": self.admin_url,
            "KRATOS_PUBLIC_URL": self.public_url,
            "IDP_CONFIGMAP_NAME": self.idp_configmap_name,
            "IDP_CONFIGMAP_NAMESPACE": self.idp_configmap_namespace,
            "SCHEMAS_CONFIGMAP_NAME": self.schemas_configmap_name,
            "SCHEMAS_CONFIGMAP_NAMESPACE": self.schemas_configmap_namespace,
        }

    @classmethod
    def load(cls, requirer: KratosInfoRequirer) -> "KratosData":
        if not requirer.is_ready():
            return KratosData()

        provider_data = requirer.get_kratos_info() or {}
        return KratosData(
            admin_url=provider_data.get("admin_endpoint", ""),
            public_url=provider_data.get("public_endpoint", ""),
            idp_configmap_name=provider_data.get("providers_configmap_name", ""),
            idp_configmap_namespace=provider_data.get("configmaps_namespace", ""),
            schemas_configmap_name=provider_data.get("schemas_configmap_name", ""),
            schemas_configmap_namespace=provider_data.get("configmaps_namespace", ""),
        )


@dataclass(frozen=True)
class HydraData:
    """The data source from the hydra-endpoint-info integration."""

    admin_url: str = ""

    def to_env_vars(self) -> EnvVars:
        return {
            "HYDRA_ADMIN_URL": self.admin_url,
        }

    @classmethod
    def load(cls, requirer: HydraEndpointsRequirer) -> "HydraData":
        try:
            endpoints = requirer.get_hydra_endpoints()
        except Exception as e:
            logger.error("hydra-endpoint-info integration not ready: %s", e)
            return HydraData()

        return HydraData(
            admin_url=endpoints["admin_endpoint"],
        )


@dataclass(frozen=True)
class OathkeeperData:
    """The data source from the Oathkeeper integration."""

    public_url: str = ""
    rules_configmap_name: str = ""
    rules_configmap_namespace: str = ""

    def to_env_vars(self) -> EnvVars:
        return {
            "OATHKEEPER_PUBLIC_URL": self.public_url,
            "RULES_CONFIGMAP_NAME": self.rules_configmap_name,
            "RULES_CONFIGMAP_NAMESPACE": self.rules_configmap_namespace,
        }

    @classmethod
    def load(cls, requirer: OathkeeperInfoRequirer) -> "OathkeeperData":
        if not requirer.is_ready():
            return OathkeeperData()

        data = requirer.get_oathkeeper_info() or {}
        return OathkeeperData(
            public_url=data.get("public_endpoint", ""),
            rules_configmap_name=data.get("rules_configmap_name", ""),
            rules_configmap_namespace=data.get("configmaps_namespace", ""),
        )


@dataclass(frozen=True)
class TracingData:
    """The data source from the tracing integration."""

    is_ready: bool = False
    http_endpoint: str = ""
    grpc_endpoint: str = ""

    def to_env_vars(self) -> EnvVars:
        return {
            "TRACING_ENABLED": self.is_ready,
            "OTEL_HTTP_ENDPOINT": self.http_endpoint,
            "OTEL_GRPC_ENDPOINT": self.grpc_endpoint,
        }

    @classmethod
    def load(cls, requirer: TracingEndpointRequirer) -> "TracingData":
        if not (is_ready := requirer.is_ready()):
            return TracingData()

        return TracingData(
            is_ready=is_ready,
            http_endpoint=requirer.otlp_http_endpoint(),  # type: ignore[arg-type]
            grpc_endpoint=requirer.otlp_grpc_endpoint(),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class IngressData:
    """The data source from the ingress integration."""

    is_ready: bool = False
    url: str = f"http://{socket.getfqdn()}:{ADMIN_SERVICE_PORT}"

    def to_env_vars(self) -> EnvVars:
        return {
            "CONTEXT_PATH": urlparse(self.url).path,
            "OAUTH2_REDIRECT_URI": join(self.url, OAUTH_CALLBACK_PATH),
        }

    @classmethod
    def load(cls, requirer: IngressPerAppRequirer) -> "IngressData":
        if not (is_ready := requirer.is_ready()):
            return IngressData()

        return IngressData(is_ready=is_ready, url=requirer.url)  # type: ignore[arg-type]


@dataclass(frozen=True)
class OAuthProviderData:
    """The data source from the oauth integration."""

    auth_enabled: bool = False
    oidc_issuer_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    access_token_verification_strategy: str = DEFAULT_ACCESS_TOKEN_VERIFICATION_STRATEGY

    def to_env_vars(self) -> EnvVars:
        return {
            "AUTHENTICATION_ENABLED": self.auth_enabled,
            "OIDC_ISSUER": self.oidc_issuer_url,
            "OAUTH2_CLIENT_ID": self.client_id,
            "OAUTH2_CLIENT_SECRET": self.client_secret,
            "OAUTH2_CODEGRANT_SCOPES": OAUTH_SCOPES,
            "ACCESS_TOKEN_VERIFICATION_STRATEGY": self.access_token_verification_strategy,
        }


class OAuthIntegration:
    def __init__(self, requirer: OAuthRequirer) -> None:
        self._requirer = requirer

    def is_ready(self) -> bool:
        return True if self._requirer.get_provider_info() else False

    @property
    def oauth_provider_data(self) -> OAuthProviderData:
        if not (auth_enabled := self._requirer.is_client_created()):
            return OAuthProviderData()

        oauth_provider_info = self._requirer.get_provider_info()
        return OAuthProviderData(
            auth_enabled=auth_enabled,
            oidc_issuer_url=oauth_provider_info.issuer_url,  # type: ignore[union-attr]
            client_id=oauth_provider_info.client_id,  # type: ignore
            client_secret=oauth_provider_info.client_secret,  # type: ignore
            access_token_verification_strategy="jwks"
            if oauth_provider_info.jwt_access_token  # type: ignore[union-attr]
            else DEFAULT_ACCESS_TOKEN_VERIFICATION_STRATEGY,
        )

    def update_oauth_client_config(self, ingress_url: str) -> None:
        client_config = load_oauth_client_config(ingress_url, self._requirer)
        self._requirer.update_client_config(client_config)


@dataclass(frozen=True)
class TLSCertificates:
    ca_bundle: str

    @classmethod
    def load(cls, requirer: CertificateTransferRequires) -> "TLSCertificates":
        """Fetch the CA certificates from all "receive-ca-cert" integrations.

        Compose the trusted CA certificates in /etc/ssl/certs/ca-certificates.crt.
        """
        # deal with v1 relations
        ca_certs = requirer.get_all_certificates()

        # deal with v0 relations
        cert_transfer_integrations = requirer.charm.model.relations[
            CERTIFICATE_TRANSFER_INTEGRATION_NAME
        ]

        for integration in cert_transfer_integrations:
            ca = {
                integration.data[unit]["ca"]
                for unit in integration.units
                if "ca" in integration.data[unit]
            }
            ca_certs.update(ca)

        ca_bundle = "\n".join(ca_certs)

        return cls(ca_bundle=ca_bundle)


# TODO(dushu) Remove when audience issue is fixed in login-ui
def load_oauth_client_config(
    ingress_url: str,
    oauth_requirer: Optional[OAuthRequirer] = None,
) -> ClientConfig:
    """The temporary factory of the ClientConfig provided to the oauth integration."""
    client = ClientConfig(
        redirect_uri=join(ingress_url, OAUTH_CALLBACK_PATH),
        scope=OAUTH_SCOPES,
        grant_types=OAUTH_GRANT_TYPES,
    )

    # Bootstrap the client config to have the client_id as an aud.
    # TODO(nsklikas): Remove when the login-ui automatically adds it to the audience
    # https://github.com/canonical/identity-platform-login-ui/issues/244
    if not oauth_requirer:
        return client

    oauth_provider_data = oauth_requirer.get_provider_info()
    if oauth_provider_data and oauth_provider_data.client_id:
        client.audience = [oauth_provider_data.client_id]

    return client
