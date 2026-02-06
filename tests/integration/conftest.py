# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import os
import re
import secrets
import subprocess
from contextlib import suppress
from pathlib import Path
from time import sleep
from typing import Callable, Generator

import jubilant
import pytest
from integration.constants import (
    ADMIN_SERVICE_APP,
    ADMIN_SERVICE_IMAGE,
    CERTIFICATE_TRANSFER_INTEGRATION_NAME,
    DATABASE_INTEGRATION_NAME,
    DB_APP,
    HYDRA_ENDPOINTS_INTEGRATION_NAME,
    INGRESS_INTEGRATION_NAME,
    KRATOS_INFO_INTEGRATION_NAME,
    MAIL_HTTP_PORT,
    MAIL_IMAGE,
    MAIL_SMTP_PORT,
    OPENFGA_APP,
    OPENFGA_INTEGRATION_NAME,
    SMTP_INTEGRATOR_APP,
)
from integration.utils import (
    get_app_integration_data,
    juju_model_factory,
)
from lightkube import Client, KubeConfig
from lightkube.models.apps_v1 import DeploymentSpec
from lightkube.models.core_v1 import (
    Container,
    ContainerPort,
    PodSpec,
    PodTemplateSpec,
    ServicePort,
    ServiceSpec,
)
from lightkube.models.meta_v1 import LabelSelector, ObjectMeta
from lightkube.resources.apps_v1 import Deployment
from lightkube.resources.core_v1 import Service


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--keep-models",
        "--no-teardown",
        action="store_true",
        dest="no_teardown",
        default=False,
        help="Keep the model after the test is finished.",
    )
    parser.addoption(
        "--model",
        action="store",
        dest="model",
        default=None,
        help="The model to run the tests on.",
    )
    parser.addoption(
        "--no-deploy",
        "--no-setup",
        action="store_true",
        dest="no_setup",
        default=False,
        help="Skip deployment of the charm.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "setup: tests that setup some parts of the environment")
    config.addinivalue_line("markers", "upgrade: tests that upgrade the charm")
    config.addinivalue_line(
        "markers", "teardown: tests that teardown some parts of the environment."
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    skip_setup = pytest.mark.skip(reason="no_setup provided")
    skip_teardown = pytest.mark.skip(reason="no_teardown provided")
    for item in items:
        if config.getoption("no_setup") and "setup" in item.keywords:
            item.add_marker(skip_setup)
        if config.getoption("no_teardown") and "teardown" in item.keywords:
            item.add_marker(skip_teardown)


@pytest.fixture(scope="module")
def juju(request: pytest.FixtureRequest) -> Generator[jubilant.Juju, None, None]:
    """Create a temporary Juju model for integration tests."""
    model_name = request.config.getoption("--model")
    if not model_name:
        model_name = f"test-admin-ui-{secrets.token_hex(4)}"

    juju_ = juju_model_factory(model_name)
    juju_.wait_timeout = 10 * 60

    try:
        yield juju_
    finally:
        if request.session.testsfailed:
            log = juju_.debug_log(limit=1000)
            print(log, end="")

        no_teardown = bool(request.config.getoption("--no-teardown"))
        keep_model = no_teardown or request.session.testsfailed > 0
        if not keep_model:
            with suppress(jubilant.CLIError):
                args = [
                    "destroy-model",
                    juju_.model,
                    "--no-prompt",
                    "--destroy-storage",
                    "--force",
                    "--timeout",
                    "600s",
                ]
                juju_.cli(*args, include_model=False)


@pytest.fixture(scope="session")
def local_charm() -> Path:
    """Get the path to the charm-under-test."""
    charm: str | Path | None = os.getenv("CHARM_PATH")
    if not charm:
        subprocess.run(["charmcraft", "pack"], check=True)
        if not (charms := list(Path(".").glob("*.charm"))):
            raise RuntimeError("Charm not found and build failed")
        charm = charms[0].absolute()
    return Path(charm)


def integrate_dependencies(
    juju: jubilant.Juju,
    kratos_app_name: str,
    hydra_app_name: str,
    public_ingress_name: str,
    self_signed_certificates_app_name: str,
) -> None:
    juju.integrate(f"{ADMIN_SERVICE_APP}:{DATABASE_INTEGRATION_NAME}", DB_APP)
    juju.integrate(
        f"{ADMIN_SERVICE_APP}:{KRATOS_INFO_INTEGRATION_NAME}",
        f"{kratos_app_name}:{KRATOS_INFO_INTEGRATION_NAME}",
    )
    juju.integrate(
        f"{ADMIN_SERVICE_APP}:{HYDRA_ENDPOINTS_INTEGRATION_NAME}",
        f"{hydra_app_name}:{HYDRA_ENDPOINTS_INTEGRATION_NAME}",
    )
    juju.integrate(f"{ADMIN_SERVICE_APP}:oauth", f"{hydra_app_name}:oauth")
    juju.integrate(
        f"{ADMIN_SERVICE_APP}:{INGRESS_INTEGRATION_NAME}",
        f"{public_ingress_name}:{INGRESS_INTEGRATION_NAME}",
    )
    juju.integrate(f"{ADMIN_SERVICE_APP}:{OPENFGA_INTEGRATION_NAME}", OPENFGA_APP)
    juju.integrate(
        f"{ADMIN_SERVICE_APP}:{CERTIFICATE_TRANSFER_INTEGRATION_NAME}",
        self_signed_certificates_app_name,
    )
    juju.integrate(ADMIN_SERVICE_APP, f"{SMTP_INTEGRATOR_APP}:smtp")


@pytest.fixture
def app_integration_data(juju: jubilant.Juju) -> Callable:
    def _get_data(app_name: str, integration_name: str, unit_num: int = 0):
        return get_app_integration_data(juju, app_name, integration_name, unit_num)

    return _get_data


@pytest.fixture
def leader_kratos_integration_data(
    app_integration_data: Callable, kratos_app_name: str
) -> dict | None:
    return app_integration_data(ADMIN_SERVICE_APP, KRATOS_INFO_INTEGRATION_NAME)


@pytest.fixture
def leader_hydra_endpoint_integration_data(
    app_integration_data: Callable, hydra_app_name: str
) -> dict | None:
    return app_integration_data(ADMIN_SERVICE_APP, HYDRA_ENDPOINTS_INTEGRATION_NAME)


@pytest.fixture
def leader_openfga_integration_data(app_integration_data: Callable) -> dict | None:
    return app_integration_data(ADMIN_SERVICE_APP, OPENFGA_INTEGRATION_NAME)


@pytest.fixture
def leader_ingress_integration_data(
    app_integration_data: Callable, public_traefik_app_name: str
) -> dict | None:
    return app_integration_data(ADMIN_SERVICE_APP, INGRESS_INTEGRATION_NAME)


@pytest.fixture
def leader_oauth_integration_data(
    app_integration_data: Callable, hydra_app_name: str
) -> dict | None:
    return app_integration_data(ADMIN_SERVICE_APP, "oauth")


@pytest.fixture
def leader_peer_integration_data(app_integration_data: Callable) -> dict | None:
    return app_integration_data(ADMIN_SERVICE_APP, ADMIN_SERVICE_APP)


@pytest.fixture
def leader_smtp_integration_data(app_integration_data: Callable) -> dict | None:
    return app_integration_data(ADMIN_SERVICE_APP, "smtp")


@pytest.fixture
def leader_database_integration_data(app_integration_data: Callable) -> dict | None:
    return app_integration_data(ADMIN_SERVICE_APP, DATABASE_INTEGRATION_NAME)


@pytest.fixture(scope="session")
def admin_service_version() -> str:
    matched = re.search(r"v(?P<version>\d+\.\d+\.\d+)", ADMIN_SERVICE_IMAGE)
    return matched.group("version") if matched else ""


@pytest.fixture(scope="module")
def mail_deployment(juju: jubilant.Juju) -> None:
    client = Client(config=KubeConfig.from_file("~/.kube/config"))

    deployment = Deployment(
        metadata=ObjectMeta(name="mail", namespace=juju.model),
        spec=DeploymentSpec(
            replicas=1,
            selector=LabelSelector(matchLabels={"app": "mail"}),
            template=PodTemplateSpec(
                metadata=ObjectMeta(labels={"app": "mail"}),
                spec=PodSpec(
                    containers=[
                        Container(
                            name="mail",
                            image=MAIL_IMAGE,
                            ports=[
                                ContainerPort(containerPort=MAIL_SMTP_PORT),
                                ContainerPort(containerPort=MAIL_HTTP_PORT),
                            ],
                        )
                    ]
                ),
            ),
        ),
    )

    service = Service(
        metadata=ObjectMeta(name="mail", namespace=juju.model),
        spec=ServiceSpec(
            ports=[
                ServicePort(port=MAIL_SMTP_PORT, targetPort=MAIL_SMTP_PORT, name="smtp"),
                ServicePort(port=MAIL_HTTP_PORT, targetPort=MAIL_HTTP_PORT, name="http"),
            ],
            selector={"app": "mail"},
        ),
    )

    # Apply the resources
    client.apply(deployment, field_manager="mail")
    client.apply(service, namespace=juju.model, field_manager="mail")

    # Wait for the deployment to be ready
    max_retries = 10
    for _ in range(max_retries):
        mail_deployment = client.get(Deployment, name="mail", namespace=juju.model)
        if not mail_deployment.status or not mail_deployment.status.readyReplicas:
            sleep(10)
            continue
        break
    else:
        raise TimeoutError(f"Mail service not ready after {max_retries} retries.")


# Fixture to provide app names that are usually in bundle
@pytest.fixture(scope="module")
def openfga_app_name() -> str:
    return OPENFGA_APP


@pytest.fixture(scope="module")
def db_app_name() -> str:
    return DB_APP


@pytest.fixture(scope="module")
def kratos_app_name() -> str:
    return "kratos"


@pytest.fixture(scope="module")
def hydra_app_name() -> str:
    return "hydra"


@pytest.fixture(scope="module")
def public_traefik_app_name() -> str:
    return "traefik-public"


@pytest.fixture(scope="module")
def self_signed_certificates_app_name() -> str:
    return "self-signed-certificates"
