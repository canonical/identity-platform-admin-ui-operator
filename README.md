# Identity Platform Admin UI Charmed Operator

[![CharmHub Badge](https://charmhub.io/identity-platform-admin-ui/badge.svg)](https://charmhub.io/identity-platform-admin-ui)
[![Juju](https://img.shields.io/badge/Juju%20-3.0+-%23E95420)](https://github.com/juju/juju)
[![License](https://img.shields.io/github/license/canonical/identity-platform-admin-ui-operator?label=License)](https://github.com/canonical/identity-platform-admin-ui-operator/blob/main/LICENSE)

[![Continuous Integration Status](https://github.com/canonical/identity-platform-admin-ui-operator/actions/workflows/on_push.yaml/badge.svg?branch=main)](https://github.com/canonical/identity-platform-admin-ui-operator/actions?query=branch%3Amain)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-%23FE5196.svg)](https://conventionalcommits.org)

## Description

This repository hosts a Juju Kubernetes Charmed Operator for
the [Identity Platform Admin UI application](https://github.com/canonical/identity-platform-admin-ui).

## Usage

The `identity-platform-admin-ui` operator can be deployed using the following
command:

```shell
juju deploy identity-platform-admin-ui --channel edge --trust
```

## Integrations

Please refer to the [`charmcraft.yaml`](./charmcraft.yaml) for all required and
provided integrations.

### `kratos_info` Integration

```shell
juju integrate identity-platform-admin-ui:kratos-info kratos
```

### `hydra_endpoint_info` Integration

```shell
juju integrate identity-platform-admin-ui:hydra-endpoint-info hydra
```

### `openfga` Integration

```shell
juju integrate identity-platform-admin-ui openfga-k8s
```

### `ingress` Integration

```shell
juju integrate identity-platform-admin-ui:ingress traefik-k8s
```

### `oauth` Integration

```shell
juju integrate identity-platform-admin-ui:oauth hydra
```

### `certificate_transfer` integration

If the `oauth` integration is built, please also integrate with a CA issuer
charmed operator,
e.g. [`self-signed-certificates` operator](https://github.com/canonical/self-signed-certificates-operator):

```shell
juju integrate identity-platform-admin-ui:receive-ca-cert self-signed-certificates
```

### `smtp` integration

An `smtp` integration is necessary for `identity-platform-admin-ui` service
to be fully functional:

```shell
juju config smtp-integrator host=<smtp-server-host> port=<smtp-port>

juju integrate identity-platform-admin-ui:smtp smtp-integrator:smtp
```

## Actions

The `identity-platform-admin-ui` charmed operator offers the following Juju actions.

### `create-identity`

The `create-identity` action initiates the user invitation flow.

```shell
juju run identity-platform-admin-ui/0 create-identity schema=<identity-schema-id> traits.email=<email> password=<password>
```

## Security

Please see [SECURITY.md](https://github.com/canonical/identity-platform-admin-ui-operator/blob/main/SECURITY.md)
for guidelines on reporting security issues.

## Contributing

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines on
enhancements to this charm following best practice guidelines,
and [CONTRIBUTING.md](https://github.com/canonical/identity-platform-admin-ui-operator/blob/main/CONTRIBUTING.md)
for developer guidance.

## License

The Identity Platform Admin UI Charmed Operator is a free software, distributed
under the Apache Software License, version 2.0.
See [LICENSE](https://github.com/canonical/identity-platform-admin-ui-operator/blob/main/LICENSE)
for more information.
