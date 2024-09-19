# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more about testing at: https://juju.is/docs/sdk/testing

from unittest.mock import patch

from ops.testing import ActionFailed, Harness


class TestCreateIdentityAction:
    def test_create_identity_failed(self, harness: Harness) -> None:
        with patch("charm.CommandLine.create_identity", return_value=None):
            try:
                harness.run_action(
                    "create-identity",
                    {
                        "traits": {"email": "test@canonical.com"},
                        "schema": "schema",
                        "password": "password",
                    },
                )
            except ActionFailed as err:
                assert "Failed to create the identity. Please check the juju logs" in err.message

    def test_create_identity_success(self, harness: Harness) -> None:
        expected = "created-identity-id"
        with patch("charm.CommandLine.create_identity", return_value=expected) as mocked_cli:
            output = harness.run_action(
                "create-identity",
                {
                    "traits": {"email": "test@canonical.com"},
                    "schema": "schema",
                    "password": "password",
                },
            )

        mocked_cli.assert_called_once()
        assert output.results["identity-id"] == expected
