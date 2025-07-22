# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Constants for the charm."""

from pathlib import PurePath
from string import Template

# Charm constants
POSTGRESQL_DSN_TEMPLATE = Template("postgres://$username:$password@$endpoint/$database")
WORKLOAD_CONTAINER = "admin-ui"
WORKLOAD_SERVICE = "admin-ui"
COOKIES_ENCRYPTION_KEY = "cookies_key"
OPENFGA_MODEL_ID = "openfga_model_id"

# Application constants
ADMIN_SERVICE_COMMAND = "/usr/bin/identity-platform-admin-ui serve"
ADMIN_SERVICE_PORT = 8080
CA_CERT_DIR_PATH = PurePath("/etc/ssl/certs/")
DEFAULT_CONTEXT_PATH = ""
RULES_CONFIGMAP_FILE_NAME = "admin_ui_rules.json"
OAUTH_SCOPES = "openid,email,profile,offline_access"
OAUTH_GRANT_TYPES = ["authorization_code", "refresh_token"]
OAUTH_CALLBACK_PATH = "api/v0/auth/callback"
DEFAULT_ACCESS_TOKEN_VERIFICATION_STRATEGY = "userinfo"

# Integration constants
DATABASE_INTEGRATION_NAME = "pg-database"
PROMETHEUS_SCRAPE_INTEGRATION_NAME = "metrics-endpoint"
LOKI_API_PUSH_INTEGRATION_NAME = "logging"
GRAFANA_DASHBOARD_INTEGRATION_NAME = "grafana-dashboard"
TEMPO_TRACING_INTEGRATION_NAME = "tracing"
HYDRA_ENDPOINTS_INTEGRATION_NAME = "hydra-endpoint-info"
KRATOS_INFO_INTEGRATION_NAME = "kratos-info"
OPENFGA_INTEGRATION_NAME = "openfga"
OPENFGA_STORE_NAME = "identity-platform-admin-ui-store"
OAUTH_INTEGRATION_NAME = "oauth"
INGRESS_INTEGRATION_NAME = "ingress"
CERTIFICATE_TRANSFER_INTEGRATION_NAME = "receive-ca-cert"
SMTP_INTEGRATION_NAME = "smtp"
PEER_INTEGRATION_NAME = "identity-platform-admin-ui"
