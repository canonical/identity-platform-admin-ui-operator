# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import json
from dataclasses import replace
from unittest.mock import MagicMock, PropertyMock, create_autospec

import pytest
from charms.hydra.v0.oauth import OauthProviderConfig
from ops.model import ActiveStatus, Container, Unit
from ops.testing import Container as TestContainer
from ops.testing import Context, Exec, PeerRelation, Relation, State
from pytest_mock import MockerFixture

from charm import IdentityPlatformAdminUIOperatorCharm
from constants import DEFAULT_CONTEXT_PATH, PEER_INTEGRATION_NAME, WORKLOAD_CONTAINER
from integrations import IngressData, TLSCertificates

OAUTH_RELATION_DATA = {
    "issuer_url": "https://hydra.example.com",
    "authorization_endpoint": "https://hydra.example.com/oauth2/auth",
    "token_endpoint": "https://hydra.example.com/oauth2/token",
    "introspection_endpoint": "https://hydra.example.com/admin/oauth2/introspect",
    "userinfo_endpoint": "https://hydra.example.com/userinfo",
    "jwks_endpoint": "https://hydra.example.com/.well-known/jwks.json",
    "scope": "openid",
    "client_id": "hook-service-client-id",
    "client_secret_id": "hook-service-client-secret",
}


def create_state(
    leader: bool = True,
    relations: list | None = None,
    containers: list | None = None,
    config: dict | None = None,
) -> State:
    """Create a base State with default configuration.

    Args:
        leader: Whether this is the leader unit
        relations: List of relations to include (defaults to peer relation only)
        containers: List of containers (defaults to workload container)
        config: Charm configuration dict

    Returns:
        State object for testing
    """
    if relations is None:
        relations = [PeerRelation(PEER_INTEGRATION_NAME)]
    if containers is None:
        containers = [
            TestContainer(
                name=WORKLOAD_CONTAINER,
                can_connect=True,
                execs={
                    Exec(
                        ["hydra", "version"],
                        return_code=0,
                        stdout=(
                            "Version:    1.0.0\n"
                            "Git Hash:   43214dsfasdf431\n"
                            "Build Time: 2024-01-01T00:00:00Z"
                        ),
                    ),
                },
            )
        ]
    if config is None:
        config = {}

    return State(
        leader=leader,
        containers=containers,
        relations=relations,
        config=config,
        workload_version="1.0.0",
    )


@pytest.fixture
def context() -> Context:
    return Context(IdentityPlatformAdminUIOperatorCharm)


@pytest.fixture(autouse=True)
def mocked_k8s_resource_patch(mocker: MockerFixture) -> None:
    mock_patcher_cls = mocker.patch(
        "charms.observability_libs.v0.kubernetes_compute_resources_patch.ResourcePatcher",
        autospec=True,
    )
    mock_patcher_instance = mock_patcher_cls.return_value
    mock_patcher_instance.is_failed.return_value = (False, "")
    mock_patcher_instance.is_ready.return_value = True

    mocker.patch("charm.KubernetesComputeResourcesPatch.is_ready", return_value=True)
    mocker.patch("charm.KubernetesComputeResourcesPatch.get_status", return_value=ActiveStatus())
    mocker.patch("charm.KubernetesComputeResourcesPatch._patch", return_value=True)
    mocker.patch("charm.KubernetesComputeResourcesPatch._namespace", return_value="model")


@pytest.fixture
def mocked_workload_service(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.WorkloadService", autospec=True)


@pytest.fixture
def mocked_migration_needed(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentityPlatformAdminUIOperatorCharm.migration_needed",
        new_callable=PropertyMock,
        return_value=False,
    )


@pytest.fixture
def mocked_workload_service_version(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.WorkloadService.version", new_callable=PropertyMock, return_value="1.10.0"
    )


@pytest.fixture
def mocked_pebble_service(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.PebbleService", autospec=True)


@pytest.fixture
def mocked_oauth_integration(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.OAuthIntegration", autospec=True)


@pytest.fixture
def mocked_oauth_get_provider(mocker: MockerFixture) -> OauthProviderConfig:
    data = {
        "client_secret": "hook-service-client-secret",
        "jwt_access_token": True,
        **OAUTH_RELATION_DATA,
    }
    data.pop("client_secret_id")
    return mocker.patch(
        "charm.OAuthRequirer.get_provider_info",
        return_value=OauthProviderConfig(**data),
    )


@pytest.fixture
def mocked_openfga_store_ready(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.OpenFGAIntegration.is_store_ready", return_value=True)


@pytest.fixture
def mocked_charm_holistic_handler(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.IdentityPlatformAdminUIOperatorCharm._holistic_handler")


@pytest.fixture
def mocked_is_running(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.WorkloadService.is_running", return_value=True)


@pytest.fixture
def mocked_ingress_data(mocker: MockerFixture) -> IngressData:
    mocked = mocker.patch(
        "charm.IngressData.load",
        return_value=IngressData(is_ready=True, url=DEFAULT_CONTEXT_PATH),
    )
    return mocked.return_value


@pytest.fixture
def mocked_container() -> MagicMock:
    return create_autospec(Container)


@pytest.fixture
def mocked_unit(mocked_container: MagicMock) -> MagicMock:
    mocked = create_autospec(Unit)
    mocked.get_container.return_value = mocked_container
    return mocked


@pytest.fixture
def all_satisfied_conditions(mocker: MockerFixture) -> None:
    mocker.patch("charm.container_connectivity", return_value=True)
    mocker.patch("charm.peer_integration_exists", return_value=True)
    mocker.patch("charm.kratos_integration_exists", return_value=True)
    mocker.patch("charm.hydra_integration_exists", return_value=True)
    mocker.patch("charm.oauth_integration_exists", return_value=True)
    mocker.patch("charm.openfga_integration_exists", return_value=True)
    mocker.patch("charm.ingress_integration_exists", return_value=True)
    mocker.patch("charm.database_integration_exists", return_value=True)
    mocker.patch("charm.migration_needed_on_non_leader", return_value=False)
    mocker.patch("charm.migration_needed_on_leader", return_value=False)
    mocker.patch("charm.ca_certificate_exists", return_value=True)
    mocker.patch("charm.smtp_integration_exists", return_value=True)
    mocker.patch("charm.openfga_store_readiness", return_value=True)
    mocker.patch("charm.openfga_model_readiness", return_value=True)
    mocker.patch("charm.WorkloadService.is_failing", return_value=False)


@pytest.fixture
def mocked_open_port(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.WorkloadService.open_port")


@pytest.fixture
def mocked_version(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.WorkloadService.version", new_callable=PropertyMock, return_value="1.0.0"
    )


@pytest.fixture
def mocked_openfga_store_not_ready(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.OpenFGAIntegration.is_store_ready", return_value=False)


@pytest.fixture
def mocked_create_openfga_model(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.WorkloadService.create_openfga_model", return_value="model-id")


@pytest.fixture
def mocked_tls_certificates(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.TLSCertificates.load",
        return_value=TLSCertificates(ca_bundle="some-bundle"),
    )


@pytest.fixture
def mocked_ingress_data_load(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IngressData.load",
        return_value=IngressData(is_ready=True, url="http://test.url"),
    )


@pytest.fixture
def mocked_oauth_update(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.OAuthIntegration.update_oauth_client_config")


@pytest.fixture
def mocked_kratos_exists(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.kratos_integration_exists", return_value=True)


@pytest.fixture
def mocked_holistic_handler_patch(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.IdentityPlatformAdminUIOperatorCharm._holistic_handler")


@pytest.fixture
def mocked_ca_bundle(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.TLSCertificates.load",
        return_value=TLSCertificates(ca_bundle="mocked_ca_bundle"),
    )


@pytest.fixture
def migration_not_needed(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentityPlatformAdminUIOperatorCharm.migration_needed",
        new_callable=PropertyMock,
        return_value=False,
    )


@pytest.fixture
def mocked_cli(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.CommandLine.migrate_up")


@pytest.fixture
def peer_relation() -> PeerRelation:
    """Empty peer relation."""
    return PeerRelation(PEER_INTEGRATION_NAME, PEER_INTEGRATION_NAME)


@pytest.fixture
def peer_relation_ready(peer_relation: PeerRelation) -> PeerRelation:
    """Peer relation with local app data indicating migration version."""
    return replace(
        peer_relation,
        local_app_data={
            "migration_version_0": json.dumps("1.0.0"),
            "cookies_key": json.dumps("test-cookies-key"),
        },
    )


@pytest.fixture
def pg_database_relation() -> Relation:
    """Empty PostgreSQL database relation."""
    return Relation("pg-database", "postgresql")


@pytest.fixture
def pg_database_relation_ready(pg_database_relation: Relation) -> Relation:
    """PostgreSQL database relation with connection data."""
    return replace(
        pg_database_relation,
        remote_app_data={
            "database": "admin_ui_db",
            "endpoints": "postgresql:5432",
            "username": "admin_ui_user",
            "password": "secret_password",
        },
    )


@pytest.fixture
def hydra_endpoint_relation() -> Relation:
    """Empty Hydra endpoint relation."""
    return Relation("hydra-endpoint-info", "hydra")


@pytest.fixture
def hydra_endpoint_relation_ready(hydra_endpoint_relation: Relation) -> Relation:
    """Hydra endpoint relation with endpoint data."""
    return replace(
        hydra_endpoint_relation,
        remote_app_data={
            "admin_endpoint": "http://hydra-admin:4445",
            "public_endpoint": "http://hydra-public:4444",
        },
    )


@pytest.fixture
def kratos_info_relation() -> Relation:
    """Empty Kratos info relation."""
    return Relation("kratos-info", "kratos")


@pytest.fixture
def kratos_info_relation_ready(kratos_info_relation: Relation) -> Relation:
    """Kratos info relation with endpoint data."""
    return replace(
        kratos_info_relation,
        remote_app_data={
            "admin_endpoint": "http://kratos-admin:4434",
            "public_endpoint": "http://kratos-public:4433",
            "login_browser_endpoint": "http://kratos:4433/self-service/login/browser",
            "sessions_endpoint": "http://kratos:4433/sessions/whoami",
        },
    )


@pytest.fixture
def ingress_relation() -> Relation:
    """Empty ingress relation."""
    return Relation("ingress", "traefik")


@pytest.fixture
def ingress_relation_ready(ingress_relation: Relation) -> Relation:
    """Ingress relation with URL data."""
    return replace(
        ingress_relation,
        remote_app_data={
            "ingress": '{"url": "http://admin-ui.local"}',
        },
    )


@pytest.fixture
def openfga_relation() -> Relation:
    """Empty OpenFGA relation."""
    return Relation("openfga", "openfga")


@pytest.fixture
def openfga_relation_ready(openfga_relation: Relation) -> Relation:
    """OpenFGA relation with store data."""
    return replace(
        openfga_relation,
        remote_app_data={
            "store_id": "test-store-id",
            "token": "test-token",
            "grpc_api_url": "http://openfga:8081",
            "http_api_url": "http://openfga:8080",
        },
    )


@pytest.fixture
def oauth_relation() -> Relation:
    """Empty OAuth relation."""
    return Relation("oauth", "hydra")


@pytest.fixture
def oauth_relation_ready(oauth_relation: Relation) -> Relation:
    """OAuth relation with client credentials."""
    return replace(
        oauth_relation,
        remote_app_data=OAUTH_RELATION_DATA,
    )


@pytest.fixture
def ca_cert_relation() -> Relation:
    """Empty CA certificate relation."""
    return Relation("receive-ca-cert", "ca-provider")


@pytest.fixture
def ca_cert_relation_ready(ca_cert_relation: Relation) -> Relation:
    """CA certificate relation with certificate data."""
    return replace(
        ca_cert_relation,
        remote_app_data={
            "ca": "-----BEGIN CERTIFICATE-----\ntest-ca-cert\n-----END CERTIFICATE-----",
        },
    )


@pytest.fixture
def smtp_relation() -> Relation:
    """Empty SMTP relation."""
    return Relation("smtp", "smtp-integrator")


@pytest.fixture
def smtp_relation_ready(smtp_relation: Relation) -> Relation:
    """SMTP relation with server configuration."""
    return replace(
        smtp_relation,
        remote_app_data={
            "host": "smtp.example.com",
            "port": "587",
            "user": "smtp-user",
            "password": "smtp-password",
        },
    )
