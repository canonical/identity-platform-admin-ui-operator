# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Constants for the charm."""

from pathlib import PurePath

# Charm Constants
SERVICE_NAME = "admin-ui"

# Application Constants
ADMIN_UI_COMMAND = "/usr/bin/identity-platform-admin-ui"
LOG_DIR = PurePath("/var/log")
LOG_FILE = LOG_DIR / "admin_ui.log"

# Relation Constants
PROMETHEUS_SCRAPE_INTEGRATION_NAME = "metrics-endpoint"
LOKI_API_PUSH_INTEGRATION_NAME = "logging"
GRAFANA_DASHBOARD_INTEGRATION_NAME = "grafana-dashboard"
TEMPO_TRACING_INTEGRATION_NAME = "tracing"
HYDRA_ADMIN_UI_RELATION_NAME = "hydra-admin-endpoint"
KRATOS_ADMIN_UI_RELATION_NAME = "kratos-admin-endpoint"
OAUTHKEEPER_ADMIN_UI_RELATION_NAME = "oathkeeper-admin-endpoint"
