# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Constants for the charm."""

from pathlib import PurePath

# Charm constants
WORKLOAD_CONTAINER_NAME = "admin-ui"
WORKLOAD_SERVICE_NAME = "admin-ui"

# Application constants
ADMIN_UI_COMMAND = "/usr/bin/identity-platform-admin-ui serve"
ADMIN_UI_PORT = 8080
LOG_DIR = PurePath("/var/log")
LOG_FILE = LOG_DIR / "admin_ui.log"
RULES_CONFIGMAP_FILE_NAME = "admin_ui_rules.json"

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
PEER = "identity-platform-admin-ui"
