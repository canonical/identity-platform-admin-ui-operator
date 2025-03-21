/**
 * # Terraform Module for Identity Platform Admin UI Operator
 *
 * This is a Terraform module facilitating the deployment of the
 * identity-platform-admin-ui charm using the Juju Terraform provider.
 */

resource "juju_application" "admin_ui" {
  name        = var.app_name
  model       = var.model_name
  trust       = true
  config      = var.config
  constraints = var.constraints
  units       = var.units

  charm {
    name     = "identity-platform-admin-ui"
    base     = var.base
    channel  = var.channel
    revision = var.revision
  }
}
