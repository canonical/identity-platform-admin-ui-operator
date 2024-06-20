# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Constants for the charm."""

from pathlib import Path, PurePath

# Charm constants
WORKLOAD_CONTAINER_NAME = "admin-ui"
WORKLOAD_SERVICE_NAME = "admin-ui"

# Application constants
ADMIN_UI_COMMAND = "/usr/bin/identity-platform-admin-ui serve"
ADMIN_UI_PORT = 8080
LOG_DIR = PurePath("/var/log")
LOG_FILE = LOG_DIR / "admin_ui.log"
RULES_CONFIGMAP_FILE_NAME = "admin_ui_rules.json"
OAUTH_SCOPES = "openid,email,profile,offline_access"
OAUTH_GRANT_TYPES = ["authorization_code", "refresh_token"]
OAUTH_CALLBACK_PATH = "api/v0/auth/callback"

# Relation constants
PROMETHEUS_SCRAPE_INTEGRATION_NAME = "metrics-endpoint"
LOKI_API_PUSH_INTEGRATION_NAME = "logging"
GRAFANA_DASHBOARD_INTEGRATION_NAME = "grafana-dashboard"
TEMPO_TRACING_INTEGRATION_NAME = "tracing"
HYDRA_ENDPOINTS_INTEGRATION_NAME = "hydra-endpoint-info"
KRATOS_INFO_INTEGRATION_NAME = "kratos-info"
OATHKEEPER_INFO_INTEGRATION_NAME = "oathkeeper-info"
OPENFGA_INTEGRATION_NAME = "openfga"
OPENFGA_STORE_NAME = "identity-platform-admin-ui-store"
OAUTH_INTEGRATION_NAME = "oauth"
INGRESS_INTEGRATION_NAME = "ingress"
CERTIFICATE_TRANSFER_NAME = "receive-ca-cert"
PEER = "identity-platform-admin-ui"

CA_CERT_DIR_PATH = Path("/etc/ssl/certs/")
