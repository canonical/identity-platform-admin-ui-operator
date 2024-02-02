# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Constants for the charm."""

from pathlib import PurePath

# Charm constants
WORKLOAD_CONTAINER_NAME = "admin-ui"
WORKLOAD_SERVICE_NAME = "admin-ui"

# Application constants
ADMIN_UI_COMMAND = "/usr/bin/identity-platform-admin-ui"
ADMIN_UI_PORT = 8080
LOG_DIR = PurePath("/var/log")
LOG_FILE = LOG_DIR / "admin_ui.log"

# Relation constants
PROMETHEUS_SCRAPE_INTEGRATION_NAME = "metrics-endpoint"
LOKI_API_PUSH_INTEGRATION_NAME = "logging"
GRAFANA_DASHBOARD_INTEGRATION_NAME = "grafana-dashboard"
TEMPO_TRACING_INTEGRATION_NAME = "tracing"
HYDRA_ENDPOINTS_INTEGRATION_NAME = "hydra-endpoint-info"
KRATOS_ENDPOINTS_INTEGRATION_NAME = "kratos-endpoint-info"
