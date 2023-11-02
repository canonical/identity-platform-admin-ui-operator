# Identity Platform Admin UI Operator

## Description

Charmed Operator for the Identity Platform Admin UI application. This Operator only compatible with Juju deployments on Kubernetes cloud. For more information, visit [Identity Platform Admin UI](https://github.com/canonical/identity-platform-admin-ui).

## Usage
After cloning the repository, you may deploy the Identity Platform Admin UI Operator with the following commands:
```bash
charmcraft pack
juju deploy ./identity_platform_admin_ui_ubuntu-*-amd64.charm --resource oci-image=$(yq eval '.resources.oci-image.upstream-source' metadata.yaml) --trust
```

You can follow the deployment status with `watch -c juju status --color`.

## Relations

### Ingress

The Identity Platform Admin UI Operator offers integration with the [traefik-k8s-operator](https://github.com/canonical/traefik-k8s-operator) for ingress.

If you have traefik deployed and configured in your juju model, run the following command to provide ingress:

```bash
juju relate traefik-k8s identity-platform-admin-ui-operator:ingress
```

## Security

Security issues can be reported through [LaunchPad](https://wiki.ubuntu.com/DebuggingSecurity#How%20to%20File). Please do not file GitHub issues about security issues.

## Contributing

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines on enhancements to this
charm following best practice guidelines, and
[CONTRIBUTING.md](https://github.com/canonical/hydra-operator/blob/main/CONTRIBUTING.md) for developer guidance.

## License

The Charmed Hydra Operator is free software, distributed under the Apache Software License, version 2.0. See [LICENSE](https://github.com/canonical/hydra-operator/blob/main/LICENSE) for more information.