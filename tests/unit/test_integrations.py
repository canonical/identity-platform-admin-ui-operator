# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more about testing at: https://juju.is/docs/sdk/testing

from unittest.mock import MagicMock, patch

import pytest
from ops.testing import Harness
from pytest_mock import MockerFixture

from integrations import (
    OAuthIntegration,
    OAuthProviderData,
    OpenFGAIntegration,
    OpenFGAIntegrationData,
    PeerData,
)


class TestPeerData:
    @pytest.fixture
    def peer_data(self, harness: Harness) -> PeerData:
        data = PeerData(harness.model)
        data["key"] = "val"
        return data

    def test_without_peer_integration(self, harness: Harness, peer_data: PeerData) -> None:
        assert peer_data["key"] == {}

    def test_with_wrong_key(
        self, harness: Harness, peer_integration: int, peer_data: PeerData
    ) -> None:
        assert peer_data["wrong_key"] == {}

    def test_get(self, harness: Harness, peer_integration: int, peer_data: PeerData) -> None:
        assert peer_data["key"] == "val"

    def test_pop_without_peer_integration(
        self, harness: Harness, peer_integration: int, peer_data: PeerData
    ) -> None:
        harness.remove_relation(peer_integration)
        assert peer_data.pop("key") == {}

    def test_pop_with_wrong_key(
        self, harness: Harness, peer_integration: int, peer_data: PeerData
    ) -> None:
        assert peer_data.pop("wrong_key") == {}
        assert peer_data["key"] == "val"

    def test_pop(self, harness: Harness, peer_integration: int, peer_data: PeerData) -> None:
        assert peer_data.pop("key") == "val"
        assert peer_data["key"] == {}


class TestOpenFGAIntegration:
    @pytest.fixture
    def mocked_openfga_requirer(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch("charms.openfga_k8s.v1.openfga.OpenFGARequires")

    @pytest.fixture
    def openfga_integration(self, mocked_openfga_requirer: MagicMock) -> OpenFGAIntegration:
        return OpenFGAIntegration(mocked_openfga_requirer)

    @pytest.mark.parametrize(
        "store_info, expected",
        [
            (None, False),
            (MagicMock(store_id=None), False),
            (MagicMock(store_id="store_id"), True),
        ],
    )
    def test_is_store_ready(
        self,
        mocked_openfga_requirer: MagicMock,
        openfga_integration: OpenFGAIntegration,
        store_info: MagicMock,
        expected: bool,
    ) -> None:
        mocked_openfga_requirer.get_store_info.return_value = store_info
        assert openfga_integration.is_store_ready() == expected

    def test_openfga_integration_data_without_openfga_store(
        self,
        mocked_openfga_requirer: MagicMock,
        openfga_integration: OpenFGAIntegration,
    ) -> None:
        mocked_openfga_requirer.get_store_info.return_value = None
        expected = OpenFGAIntegrationData()
        assert openfga_integration.openfga_integration_data == expected

    def test_openfga_integration_data(
        self,
        mocked_openfga_requirer: MagicMock,
        openfga_integration: OpenFGAIntegration,
    ) -> None:
        mocked_openfga_requirer.get_store_info.return_value = MagicMock(
            store_id="store_id",
            token="token",
            grpc_api_url="grpc://api.openfga.com",
            http_api_url="http://api.openfga.com",
        )
        expected = OpenFGAIntegrationData(
            store_id="store_id",
            api_token="token",
            url="http://api.openfga.com",
        )
        assert openfga_integration.openfga_integration_data == expected


class TestOAuthIntegration:
    @pytest.fixture
    def mocked_oauth_requirer(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch("charms.hydra.v0.oauth.OAuthRequirer")

    @pytest.fixture
    def oauth_integration(self, mocked_oauth_requirer: MagicMock) -> OAuthIntegration:
        return OAuthIntegration(mocked_oauth_requirer)

    @pytest.mark.parametrize(
        "provider_info, expected",
        [(None, False), (MagicMock(), True)],
    )
    def test_is_ready(
        self,
        mocked_oauth_requirer: MagicMock,
        oauth_integration: OAuthIntegration,
        provider_info: MagicMock,
        expected: bool,
    ) -> None:
        mocked_oauth_requirer.get_provider_info.return_value = provider_info
        assert oauth_integration.is_ready() == expected

    def test_oauth_provider_data_without_oauth_client_created(
        self,
        mocked_oauth_requirer: MagicMock,
        oauth_integration: OAuthIntegration,
    ) -> None:
        mocked_oauth_requirer.is_client_created.return_value = False
        expected = OAuthProviderData()
        assert oauth_integration.oauth_provider_data == expected

    def test_oauth_provider_data(
        self, mocked_oauth_requirer: MagicMock, oauth_integration: OAuthIntegration
    ) -> None:
        mocked_oauth_requirer.is_client_created.return_value = True
        mocked_oauth_requirer.get_provider_info.return_value = MagicMock(
            issuer_url="issuer_url",
            client_id="client_id",
            client_secret="client_secret",
            jwt_access_token=True,
        )
        expected = OAuthProviderData(
            auth_enabled=True,
            oidc_issuer_url="issuer_url",
            client_id="client_id",
            client_secret="client_secret",
            access_token_verification_strategy="jwks",
        )

        assert oauth_integration.oauth_provider_data == expected

    @patch("integrations.load_oauth_client_config")
    def test_update_oauth_client_config(
        self,
        mock_load_oauth_client_config: MagicMock,
        mocked_oauth_requirer: MagicMock,
        oauth_integration: OAuthIntegration,
    ) -> None:
        client_config = MagicMock()
        mock_load_oauth_client_config.return_value = client_config
        ingress_url = "http://ingress.example.com"

        oauth_integration.update_oauth_client_config(ingress_url)

        mock_load_oauth_client_config.assert_called_once_with(ingress_url, mocked_oauth_requirer)
        mocked_oauth_requirer.update_client_config.assert_called_once_with(client_config)
