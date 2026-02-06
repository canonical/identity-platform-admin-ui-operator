# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path

import yaml

METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
ADMIN_SERVICE_APP: str = METADATA["name"]
ADMIN_SERVICE_IMAGE = METADATA["resources"]["oci-image"]["upstream-source"]
DB_APP = "postgresql-k8s"
OPENFGA_APP = "openfga-k8s"
SMTP_INTEGRATOR_APP = "smtp-integrator"
MAIL_APP = "mail"
MAIL_IMAGE = "mailhog/mailhog:latest"
MAIL_SMTP_PORT = 1025
MAIL_HTTP_PORT = 8025

# Constants for integration names
CERTIFICATE_TRANSFER_INTEGRATION_NAME = "receive-ca-cert"
DATABASE_INTEGRATION_NAME = "pg-database"
HYDRA_ENDPOINTS_INTEGRATION_NAME = "hydra-endpoint-info"
INGRESS_INTEGRATION_NAME = "ingress"
KRATOS_INFO_INTEGRATION_NAME = "kratos-info"
OPENFGA_INTEGRATION_NAME = "openfga"
OPENFGA_MODEL_ID = "openfga_model_id"
