# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse

from charms.hydra.v0.hydra_endpoints import HydraEndpointsRequirer
from charms.kratos.v0.kratos_info import KratosInfoRequirer
from charms.oathkeeper.v0.oathkeeper_info import OathkeeperInfoRequirer
from charms.openfga_k8s.v1.openfga import OpenFGARequires
from charms.tempo_k8s.v0.tracing import TracingEndpointRequirer
from ops.model import Model

from constants import PEER_INTEGRATION_NAME
from env_vars import EnvVars

logger = logging.getLogger(__name__)


class PeerData:
    def __init__(self, model: Model) -> None:
        self._model = model
        self._app = model.app

    def __getitem__(self, key: str) -> dict:
        if not (peers := self._model.get_relation(PEER_INTEGRATION_NAME)):
            return {}

        value = peers.data[self._app].get(key)
        return json.loads(value) if value else {}

    def __setitem__(self, key: str, value: Any) -> None:
        if not (peers := self._model.get_relation(PEER_INTEGRATION_NAME)):
            return

        peers.data[self._app][key] = json.dumps(value)

    def pop(self, key: str) -> dict:
        if not (peers := self._model.get_relation(PEER_INTEGRATION_NAME)):
            return {}

        data = peers.data[self._app].pop(key, None)
        return json.loads(data) if data else {}


@dataclass(frozen=True)
class OpenFGAModelData:
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


class KratosIntegration:
    def __init__(self, requirer: KratosInfoRequirer) -> None:
        self._kratos_requirer = requirer

    @property
    def kratos_data(self) -> KratosData:
        if not self._kratos_requirer.is_ready():
            return KratosData()

        data = self._kratos_requirer.get_kratos_info() or {}
        return KratosData(
            admin_url=data.get("admin_endpoint", ""),
            public_url=data.get("public_endpoint", ""),
            idp_configmap_name=data.get("providers_configmap_name", ""),
            idp_configmap_namespace=data.get("configmaps_namespace", ""),
            schemas_configmap_name=data.get("schemas_configmap_name", ""),
            schemas_configmap_namespace=data.get("configmaps_namespace", ""),
        )


@dataclass(frozen=True)
class HydraData:
    admin_url: str = ""

    def to_env_vars(self) -> EnvVars:
        return {
            "HYDRA_ADMIN_URL": self.admin_url,
        }


class HydraIntegration:
    def __init__(self, endpoint_requirer: HydraEndpointsRequirer) -> None:
        self._endpoint_requirer = endpoint_requirer

    @property
    def hydra_data(self) -> HydraData:
        try:
            endpoints = self._endpoint_requirer.get_hydra_endpoints()
        except Exception as e:
            logger.error("hydra-endpoint-info integration not ready: %s", e)
            return HydraData()

        return HydraData(
            admin_url=endpoints["admin_endpoint"],
        )


@dataclass(frozen=True)
class OathkeeperData:
    public_url: str = ""
    rules_configmap_name: str = ""
    rules_configmap_namespace: str = ""

    def to_env_vars(self) -> EnvVars:
        return {
            "OATHKEEPER_PUBLIC_URL": self.public_url,
            "RULES_CONFIGMAP_NAME": self.rules_configmap_name,
            "RULES_CONFIGMAP_NAMESPACE": self.rules_configmap_namespace,
        }


class OathkeeperIntegration:
    def __init__(self, requirer: OathkeeperInfoRequirer) -> None:
        self._requirer = requirer

    @property
    def oathkeeper_data(self) -> OathkeeperData:
        if not self._requirer.is_ready():
            return OathkeeperData()

        data = self._requirer.get_oathkeeper_info() or {}
        return OathkeeperData(
            public_url=data.get("public_endpoint", ""),
            rules_configmap_name=data.get("rules_configmap_name", ""),
            rules_configmap_namespace=data.get("configmaps_namespace", ""),
        )


@dataclass(frozen=True)
class TracingData:
    is_ready: bool = False
    http_endpoint: str = ""
    grpc_endpoint: str = ""

    def to_env_vars(self) -> EnvVars:
        return {
            "TRACING_ENABLED": self.is_ready,
            "OTEL_HTTP_ENDPOINT": self.http_endpoint,
            "OTEL_GRPC_ENDPOINT": self.grpc_endpoint,
        }


class TracingIntegration:
    def __init__(self, requirer: TracingEndpointRequirer) -> None:
        self._requirer = requirer

    @property
    def tracing_data(self) -> TracingData:
        if not (is_ready := self._requirer.is_ready()):
            return TracingData()

        return TracingData(
            is_ready=is_ready,
            http_endpoint=self._requirer.otlp_http_endpoint(),  # type: ignore[arg-type]
            grpc_endpoint=self._requirer.otlp_grpc_endpoint(),  # type: ignore[arg-type]
        )
