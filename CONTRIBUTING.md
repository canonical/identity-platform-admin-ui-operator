# Contributing

## Overview

This document explains the processes and practices recommended for contributing
enhancements to this operator.

- Generally, before developing bugs or enhancements to this charm, you
  should [open an issue](https://github.com/canonical/identity-platform-admin-ui-operator/issues)
  explaining your use case.
- If you would like to chat with us about charm development, you can reach us
  at [Canonical Mattermost public channel](https://chat.charmhub.io/charmhub/channels/charm-dev)
  or [Discourse](https://discourse.charmhub.io/).
- Familiarising yourself with
  the [Charmed Operator Framework](https://juju.is/docs/sdk) library
  will help you a lot when working on new features or bug fixes.
- All enhancements require review before being merged. Code review typically
  examines:
  - code quality
  - test coverage
  - user experience for Juju administrators of this charm.
- Please help us out in ensuring easy to review branches by rebasing your pull
  request branch onto the `main` branch. This also avoids merge commits and
  creates a linear Git
  commit history.

## Developing

You can use the environments created by `tox` for development. It helps install
`pre-commit`, `mypy` type checker, linting and formatting tools, as well as unit
and integration test dependencies.

```shell
tox -e dev
source .tox/dev/bin/activate
```

## Testing

```shell
tox -e fmt           # update your code according to linting rules
tox -e lint          # code style
tox -e unit          # unit tests
tox                  # runs 'fmt', 'lint', and 'unit' environments
```

It is recommended to use Multipass VM for running integration tests in a predictable environment.

```
multipass launch --cpus 4 --memory 8G --disk 50G --name charm-dev charm-dev
multipass stop charm-dev
multipass mount identity-platform-admin-ui-operator charm-dev:~/identity-platform-admin-ui-operator --type=native
multipass start charm-dev
multipass shell charm-dev
cd identity-platform-admin-ui-operator
tox -e integration
```

## Building

Build the charm using:

```shell
charmcraft pack
```

## Deploying

```shell
# Create a model
juju add-model dev

# Enable DEBUG logging
juju model-config logging-config="<root>=INFO;unit=DEBUG"

# Deploy the charm
juju deploy ./identity-platform-admin-ui*-amd64.charm --resource oci-image=$(yq eval '.resources.oci-image.upstream-source' charmcraft.yaml) --trust
```

## Canonical Contributor Agreement

Canonical welcomes contributions to Identity Platform Admin UI Operator. Please
check out our [contributor agreement](https://ubuntu.com/legal/contributors) if
you're interested in contributing to the solution.
