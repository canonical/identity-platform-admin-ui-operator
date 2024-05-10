# Identity Platform Admin UI Operator

[![Juju](https://img.shields.io/badge/Juju%20-3.0+-%23E95420)](https://github.com/juju/juju)
[![License](https://img.shields.io/github/license/canonical/identity-platform-admin-ui-operator?label=License)](https://github.com/canonical/identity-platform-admin-ui-operator/blob/main/LICENSE)

[![Continuous Integration Status](https://github.com/canonical/identity-platform-admin-ui-operator/actions/workflows/on_push.yaml/badge.svg?branch=main)](https://github.com/canonical/identity-platform-admin-ui-operator/actions?query=branch%3Amain)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-%23FE5196.svg)](https://conventionalcommits.org)

## Description

This repository hosts a Charmed Operator for the Identity Platform Admin UI
application. This Operator supports Juju deployments on Kubernetes cloud.

## Usage

After cloning the repository, you may deploy the Identity Platform Admin UI
Operator with the following commands:

```shell
charmcraft pack
juju deploy ./identity-platform-admin-ui*-amd64.charm \
  --resource oci-image=$(yq eval '.resources.oci-image.upstream-source' metadata.yaml) \
  --trust
```

You can follow the deployment status with `watch -c juju status --color`.

## Integrations

### Ingress

The Identity Platform Admin UI Operator offers integration with
the [traefik-k8s-operator](https://github.com/canonical/traefik-k8s-operator)
for ingress.

If you have traefik deployed and configured in your juju model, run the
following command to provide ingress:

```shell
juju integrate traefik-k8s identity-platform-admin-ui:ingress
```

## Security

Security issues can be reported
through [LaunchPad](https://wiki.ubuntu.com/DebuggingSecurity#How%20to%20File).
Please do not file GitHub issues about security issues.

## Contributing

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines on
enhancements to this charm following best practice guidelines,
and [CONTRIBUTING.md](https://github.com/canonical/identity-platform-admin-ui-operator/blob/main/CONTRIBUTING.md)
for developer guidance.

## License

The Charmed Identity Platform Admin UI Operator is a free software, distributed
under the Apache Software License, version 2.0.
See [LICENSE](https://github.com/canonical/identity-platform-admin-ui-operator/blob/main/LICENSE)
for more information.
