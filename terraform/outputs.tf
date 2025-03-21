# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "The Juju application name"
  value       = juju_application.admin_ui.name
}

output "requires" {
  description = "The Juju integrations that the charm requires"
  value = {
    hydra-endpoint-info = "hydra-endpoint-info"
    kratos-info         = "kratos-info"
    ingress             = "ingress"
    openfga             = "openfga"
    oauth               = "oauth"
    receive-ca-cert     = "receive-ca-cert"
    logging             = "logging"
    tracing             = "tracing"
    smtp                = "smtp"
  }
}

output "provides" {
  description = "The Juju integrations that the charm provides"
  value = {
    metrics-endpoint  = "metrics-endpoint"
    grafana-dashboard = "grafana-dashboard"
  }
}
