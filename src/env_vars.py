# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Mapping, Protocol, TypeAlias, Union

from constants import ADMIN_SERVICE_PORT, DEFAULT_CONTEXT_PATH, LOG_FILE

EnvVars: TypeAlias = Mapping[str, Union[str, bool]]

DEFAULT_CONTAINER_ENV = {
    "AUTHENTICATION_ENABLED": False,
    "AUTHORIZATION_ENABLED": True,
    "OPENFGA_AUTHORIZATION_MODEL_ID": "",
    "OPENFGA_STORE_ID": "",
    "OPENFGA_API_TOKEN": "",
    "OPENFGA_API_SCHEME": "",
    "OPENFGA_API_HOST": "",
    "KRATOS_ADMIN_URL": "",
    "KRATOS_PUBLIC_URL": "",
    "HYDRA_ADMIN_URL": "",
    "IDP_CONFIGMAP_NAME": "",
    "IDP_CONFIGMAP_NAMESPACE": "",
    "MAIL_HOST": "localhost",
    "MAIL_PORT": "1025",
    "MAIL_FROM_ADDRESS": "identity-team@canonical.com",
    "SCHEMAS_CONFIGMAP_NAME": "",
    "SCHEMAS_CONFIGMAP_NAMESPACE": "",
    "OATHKEEPER_PUBLIC_URL": "",
    "RULES_CONFIGMAP_NAME": "",
    "RULES_CONFIGMAP_NAMESPACE": "",
    "RULES_CONFIGMAP_FILE_NAME": "",
    "PORT": str(ADMIN_SERVICE_PORT),
    "TRACING_ENABLED": False,
    "OTEL_HTTP_ENDPOINT": "",
    "OTEL_GRPC_ENDPOINT": "",
    "OAUTH2_AUTH_COOKIES_ENCRYPTION_KEY": "",
    "CONTEXT_PATH": DEFAULT_CONTEXT_PATH,
    "LOG_LEVEL": "info",
    "LOG_FILE": str(LOG_FILE),
    "DEBUG": False,
}


class EnvVarConvertible(Protocol):
    """An interface enforcing the contribution to workload service environment variables."""

    def to_env_vars(self) -> EnvVars:
        pass
