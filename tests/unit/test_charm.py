# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import MagicMock, Mock, PropertyMock, patch

from conftest import create_state
from ops import ActiveStatus, BlockedStatus
from ops.testing import Container, Context, PeerRelation, Relation

from constants import WORKLOAD_CONTAINER
from exceptions import PebbleServiceError
from integrations import IngressData


class TestPebbleReadyEvent:
    def test_when_event_emitted(
        self,
        context: Context,
        mocked_version: MagicMock,
        mocked_open_port: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
        all_satisfied_conditions: None,
    ) -> None:
        state = create_state()
        container = state.get_container(WORKLOAD_CONTAINER)

        context.run(context.on.pebble_ready(container), state)

        mocked_open_port.assert_called_once()
        mocked_charm_holistic_handler.assert_called_once()
        assert mocked_version.call_count >= 1


class TestUpgradeCharmEvent:
    def test_non_leader_unit(
        self,
        context: Context,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        state = create_state(leader=False)

        context.run(context.on.upgrade_charm(), state)

        mocked_workload_service.return_value.create_openfga_model.assert_not_called()
        mocked_charm_holistic_handler.assert_not_called()

    def test_when_container_not_connected(
        self,
        context: Context,
        peer_relation: PeerRelation,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        state = create_state(
            leader=True,
            containers=[Container(name=WORKLOAD_CONTAINER, can_connect=False)],
            relations=[peer_relation],
        )

        context.run(context.on.upgrade_charm(), state)

        mocked_workload_service.return_value.create_openfga_model.assert_not_called()

    def test_when_missing_peer_integration(
        self,
        context: Context,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        state = create_state(
            leader=True,
            relations=[],
        )

        context.run(context.on.upgrade_charm(), state)

        mocked_workload_service.return_value.create_openfga_model.assert_not_called()
        mocked_charm_holistic_handler.assert_not_called()

    def test_when_openfga_store_not_ready(
        self,
        context: Context,
        mocked_openfga_store_not_ready: MagicMock,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        state = create_state()

        context.run(context.on.upgrade_charm(), state)

        mocked_workload_service.return_value.create_openfga_model.assert_not_called()
        mocked_charm_holistic_handler.assert_not_called()

    def test_upgrade_charm_success(
        self,
        context: Context,
        mocked_version: MagicMock,
        mocked_create_openfga_model: MagicMock,
        mocked_tls_certificates: MagicMock,
        all_satisfied_conditions: None,
    ) -> None:
        state = create_state()
        state_out = context.run(context.on.upgrade_charm(), state)

        assert state_out.unit_status == ActiveStatus()

        peer_rel = next(
            r for r in state_out.relations if r.endpoint == "identity-platform-admin-ui"
        )
        assert peer_rel.local_app_data["1.0.0"] == '{"openfga_model_id": "model-id"}'


class TestCollectStatusEvent:
    def test_collect_status_all_good(
        self, context: Context, all_satisfied_conditions: None
    ) -> None:
        state = create_state()
        out = context.run(context.on.collect_unit_status(), state)
        assert out.unit_status == ActiveStatus()

    def test_collect_status_missing_relations(self, context: Context) -> None:
        state = create_state()
        out = context.run(context.on.collect_unit_status(), state)
        assert out.unit_status == BlockedStatus("Missing integration kratos-info")

    def test_collect_status_next_missing(
        self, context: Context, mocked_kratos_exists: MagicMock
    ) -> None:
        state = create_state()
        out = context.run(context.on.collect_unit_status(), state)
        assert out.unit_status == BlockedStatus("Missing integration hydra-endpoint-info")


class TestOpenFGAStoreCreatedEvent:
    def test_when_container_not_connected(
        self,
        context: Context,
        peer_relation: PeerRelation,
        openfga_relation: Relation,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        state = create_state(
            leader=True,
            containers=[Container(name=WORKLOAD_CONTAINER, can_connect=False)],
            relations=[peer_relation, openfga_relation],
        )

        context.run(context.on.relation_changed(relation=openfga_relation), state)

        mocked_workload_service.return_value.create_openfga_model.assert_not_called()
        mocked_charm_holistic_handler.assert_not_called()

    def test_when_missing_peer_integration(
        self,
        context: Context,
        openfga_relation: Relation,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        state = create_state(
            leader=True,
            relations=[openfga_relation],
        )

        context.run(context.on.relation_changed(relation=openfga_relation), state)

        mocked_workload_service.return_value.create_openfga_model.assert_not_called()
        mocked_charm_holistic_handler.assert_not_called()

    def test_when_openfga_store_not_ready(
        self,
        context: Context,
        peer_relation: PeerRelation,
        openfga_relation: Relation,
        mocked_openfga_store_not_ready: MagicMock,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        state = create_state(relations=[peer_relation, openfga_relation])

        context.run(context.on.relation_changed(relation=openfga_relation), state)

        mocked_workload_service.return_value.create_openfga_model.assert_not_called()
        mocked_charm_holistic_handler.assert_not_called()

    def test_non_leader_unit(
        self,
        context: Context,
        peer_relation: PeerRelation,
        openfga_relation_ready: Relation,
        mocked_openfga_store_ready: MagicMock,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
        all_satisfied_conditions: None,
    ) -> None:
        state = create_state(leader=False, relations=[peer_relation, openfga_relation_ready])

        context.run(context.on.relation_changed(relation=openfga_relation_ready), state)

        mocked_workload_service.return_value.create_openfga_model.assert_not_called()
        mocked_charm_holistic_handler.assert_called_once()

    def test_openfga_created_event_success(
        self,
        context: Context,
        peer_relation: PeerRelation,
        openfga_relation: Relation,
        mocked_version: MagicMock,
        mocked_create_openfga_model: MagicMock,
        mocked_tls_certificates: MagicMock,
        all_satisfied_conditions: None,
    ) -> None:
        state = create_state(relations=[peer_relation, openfga_relation])

        state_out = context.run(context.on.relation_changed(relation=openfga_relation), state)

        assert state_out.unit_status == ActiveStatus()


class TestOpenFGAStoreRemovedEvent:
    def test_non_leader_unit(
        self,
        context: Context,
        mocked_version: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
        openfga_relation: Relation,
        peer_relation_ready: PeerRelation,
        all_satisfied_conditions: None,
    ) -> None:
        state = create_state(leader=False, relations=[openfga_relation, peer_relation_ready])

        context.run(context.on.relation_departed(relation=openfga_relation), state)

        mocked_charm_holistic_handler.assert_called_once()

    def test_leader_unit(
        self,
        context: Context,
        mocked_version: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
        openfga_relation: Relation,
        peer_relation: PeerRelation,
        all_satisfied_conditions: None,
    ) -> None:
        state = create_state(leader=True, relations=[openfga_relation, peer_relation])

        state_out = context.run(context.on.relation_departed(relation=openfga_relation), state)

        # Leader unit should clean up peer data
        peer_rel_out = [
            r for r in state_out.relations if r.endpoint == "identity-platform-admin-ui"
        ][0]
        # The data should be removed or empty
        if "1.0.0" in peer_rel_out.local_app_data:
            assert peer_rel_out.local_app_data["1.0.0"] == "{}"
        mocked_charm_holistic_handler.assert_called_once()


class TestIngressReadyEvent:
    def test_non_leader_unit(
        self,
        context: Context,
        peer_relation: PeerRelation,
        ingress_relation_ready: Relation,
        mocked_oauth_integration: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
        all_satisfied_conditions: None,
    ) -> None:
        state = create_state(leader=False, relations=[peer_relation, ingress_relation_ready])

        context.run(context.on.relation_changed(relation=ingress_relation_ready), state)

        mocked_oauth_integration.return_value.update_oauth_client_config.assert_not_called()
        mocked_charm_holistic_handler.assert_called_once()

    def test_leader_unit(
        self,
        context: Context,
        peer_relation: PeerRelation,
        ingress_relation_ready: Relation,
        mocked_ingress_data_load: MagicMock,
        mocked_oauth_integration: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
        all_satisfied_conditions: None,
    ) -> None:
        test_url = "http://test.url"
        mocked_ingress_data_load.return_value = IngressData(is_ready=True, url=test_url)

        state = create_state(leader=True, relations=[peer_relation, ingress_relation_ready])

        context.run(context.on.relation_changed(relation=ingress_relation_ready), state)

        mocked_oauth_integration.return_value.update_oauth_client_config.assert_called_once_with(
            ingress_url=test_url
        )
        mocked_charm_holistic_handler.assert_called_once()


class TestIngressRevokedEvent:
    def test_non_leader_unit(
        self,
        context: Context,
        peer_relation: PeerRelation,
        ingress_relation: Relation,
        mocked_oauth_integration: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        state = create_state(leader=False, relations=[peer_relation, ingress_relation])

        context.run(context.on.relation_broken(relation=ingress_relation), state)

        mocked_oauth_integration.return_value.update_oauth_client_config.assert_not_called()
        mocked_charm_holistic_handler.assert_called_once()

    def test_leader_unit(
        self,
        context: Context,
        peer_relation: PeerRelation,
        ingress_relation: Relation,
        mocked_ingress_data_load: MagicMock,
        mocked_oauth_integration: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
        all_satisfied_conditions: None,
    ) -> None:
        test_url = "http://test.url"
        mocked_ingress_data_load.return_value = IngressData(is_ready=True, url=test_url)

        state = create_state(leader=True, relations=[peer_relation, ingress_relation])

        context.run(context.on.relation_broken(relation=ingress_relation), state)

        mocked_oauth_integration.return_value.update_oauth_client_config.assert_called_once_with(
            ingress_url=test_url
        )
        mocked_charm_holistic_handler.assert_called_once()


class TestOAuthInfoChangedEvent:
    def test_non_leader_unit(
        self,
        context: Context,
        peer_relation: PeerRelation,
        oauth_relation_ready: Relation,
        mocked_oauth_integration: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
        all_satisfied_conditions: None,
    ) -> None:
        state = create_state(leader=False, relations=[peer_relation, oauth_relation_ready])

        context.run(context.on.relation_changed(relation=oauth_relation_ready), state)

        mocked_oauth_integration.return_value.update_oauth_client_config.assert_not_called()
        mocked_charm_holistic_handler.assert_called_once()

    def test_leader_unit(
        self,
        context: Context,
        peer_relation: PeerRelation,
        oauth_relation_ready: Relation,
        mocked_ingress_data_load: MagicMock,
        mocked_oauth_integration: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
        all_satisfied_conditions: None,
    ) -> None:
        test_url = "http://test.url"
        mocked_ingress_data_load.return_value = IngressData(is_ready=True, url=test_url)

        state = create_state(leader=True, relations=[peer_relation, oauth_relation_ready])

        context.run(context.on.relation_changed(relation=oauth_relation_ready), state)

        mocked_oauth_integration.return_value.update_oauth_client_config.assert_called_once_with(
            ingress_url=test_url
        )
        mocked_charm_holistic_handler.assert_called_once()


class TestOAuthInfoRemovedEvent:
    def test_non_leader_unit(
        self,
        context: Context,
        peer_relation: PeerRelation,
        oauth_relation: Relation,
        mocked_oauth_integration: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        state = create_state(leader=False, relations=[peer_relation, oauth_relation])

        context.run(context.on.relation_broken(relation=oauth_relation), state)

        mocked_oauth_integration.return_value.update_oauth_client_config.assert_not_called()
        mocked_charm_holistic_handler.assert_called_once()

    def test_leader_unit(
        self,
        context: Context,
        peer_relation: PeerRelation,
        oauth_relation: Relation,
        mocked_ingress_data_load: MagicMock,
        mocked_oauth_integration: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
        all_satisfied_conditions: None,
    ) -> None:
        test_url = "http://test.url"
        mocked_ingress_data_load.return_value = IngressData(is_ready=True, url=test_url)

        state = create_state(leader=True, relations=[peer_relation, oauth_relation])

        context.run(context.on.relation_broken(relation=oauth_relation), state)

        mocked_oauth_integration.return_value.update_oauth_client_config.assert_called_once_with(
            ingress_url=test_url
        )
        mocked_charm_holistic_handler.assert_called_once()


class TestCertificateAvailableEvent:
    def test_certificate_available_event_success(
        self,
        context: Context,
        peer_relation: PeerRelation,
        ca_cert_relation: Relation,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        state = create_state(relations=[peer_relation, ca_cert_relation])

        context.run(context.on.relation_changed(relation=ca_cert_relation), state)

        # The holistic handler should be called
        mocked_charm_holistic_handler.assert_called_once()


class TestCertificateRemovedEvent:
    def test_certificate_removed_event_success(
        self,
        context: Context,
        peer_relation: PeerRelation,
        ca_cert_relation: Relation,
        mocked_workload_service: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        state = create_state(relations=[peer_relation, ca_cert_relation])

        context.run(context.on.relation_broken(relation=ca_cert_relation), state)

        mocked_charm_holistic_handler.assert_called_once()


class TestDatabaseCreatedEvent:
    def test_database_created_event_success(
        self,
        context: Context,
        peer_relation: PeerRelation,
        pg_database_relation_ready: Relation,
        mocked_charm_holistic_handler: MagicMock,
        all_satisfied_conditions: None,
    ) -> None:
        state = create_state(relations=[peer_relation, pg_database_relation_ready])

        context.run(context.on.relation_changed(relation=pg_database_relation_ready), state)

        mocked_charm_holistic_handler.assert_called_once()


class TestDatabaseChangedEvent:
    def test_database_changed_event_success(
        self,
        context: Context,
        pg_database_relation_ready: Relation,
        mocked_charm_holistic_handler: MagicMock,
        all_satisfied_conditions: None,
    ) -> None:
        state = create_state(relations=[pg_database_relation_ready])

        context.run(context.on.relation_changed(relation=pg_database_relation_ready), state)

        mocked_charm_holistic_handler.assert_called_once()


class TestDatabaseIntegrationBrokenEvent:
    def test_database_integration_broken_event_success(
        self,
        context: Context,
        mocked_charm_holistic_handler: MagicMock,
        mocked_pebble_service: MagicMock,
        pg_database_relation: Relation,
    ) -> None:
        state = create_state(relations=[pg_database_relation])

        context.run(context.on.relation_broken(relation=pg_database_relation), state)

        mocked_charm_holistic_handler.assert_called_once()
        mocked_pebble_service.return_value.stop.assert_called_once()


class TestHolisticHandler:
    def test_when_noop_condition_failed(
        self,
        context: Context,
        mocked_workload_service: MagicMock,
    ) -> None:
        with (
            patch("charm.NOOP_CONDITIONS", new=[Mock(return_value=False)]),
            patch("charm.EVENT_DEFER_CONDITIONS", new=[Mock(return_value=True)]),
        ):
            state = create_state()
            context.run(context.on.config_changed(), state)

        mocked_workload_service.return_value.prepare_dir.assert_not_called()
        mocked_workload_service.return_value.push_ca_certs.assert_not_called()

    def test_when_event_defer_condition_failed(
        self,
        context: Context,
        mocked_workload_service: MagicMock,
    ) -> None:
        event = context.on.config_changed()
        with (
            patch("charm.NOOP_CONDITIONS", new=[Mock(return_value=True)]),
            patch("charm.EVENT_DEFER_CONDITIONS", new=[Mock(return_value=False)]),
        ):
            state = create_state()
            out_state = context.run(context.on.config_changed(), state)

        mocked_workload_service.return_value.prepare_dir.assert_not_called()
        assert out_state.deferred[0].name == event.path

    def test_when_all_conditions_satisfied(
        self,
        mocked_ca_bundle: MagicMock,
        context: Context,
        peer_relation: PeerRelation,
        kratos_info_relation_ready: Relation,
        hydra_endpoint_relation_ready: Relation,
        oauth_relation_ready: Relation,
        openfga_relation_ready: Relation,
        ingress_relation_ready: Relation,
        pg_database_relation_ready: Relation,
        mocked_oauth_get_provider: MagicMock,
        mocked_workload_service: MagicMock,
        mocked_pebble_service: MagicMock,
        mocked_migration_needed: MagicMock,
    ) -> None:
        with (
            patch("charm.NOOP_CONDITIONS", new=[Mock(return_value=True)]),
            patch("charm.EVENT_DEFER_CONDITIONS", new=[Mock(return_value=True)]),
        ):
            state = create_state(
                relations=[
                    peer_relation,
                    kratos_info_relation_ready,
                    hydra_endpoint_relation_ready,
                    oauth_relation_ready,
                    openfga_relation_ready,
                    ingress_relation_ready,
                    pg_database_relation_ready,
                ]
            )
            context.run(context.on.config_changed(), state)

        mocked_workload_service.return_value.push_ca_certs.assert_called_once_with(
            mocked_ca_bundle.return_value.ca_bundle
        )
        mocked_pebble_service.return_value.plan.assert_called_once()

    def test_when_migration_needed_non_leader_unit(
        self,
        context: Context,
        mocked_cli: MagicMock,
        mocked_pebble_service: MagicMock,
        mocked_migration_needed: MagicMock,
    ) -> None:
        mocked_migration_needed.return_value = True
        with (
            patch("charm.NOOP_CONDITIONS", new=[Mock(return_value=True)]),
            patch("charm.EVENT_DEFER_CONDITIONS", new=[Mock(return_value=True)]),
        ):
            state = create_state(leader=False)
            context.run(context.on.config_changed(), state)

        # Non-leader should not run migration
        mocked_cli.assert_not_called()
        # And should not plan
        mocked_pebble_service.return_value.plan.assert_not_called()

    def test_when_migration_needed_leader_unit(
        self,
        context: Context,
        mocked_cli: MagicMock,
        mocked_pebble_service: MagicMock,
        mocked_migration_needed: MagicMock,
        mocked_workload_service_version: MagicMock,
        peer_relation_ready: PeerRelation,
    ) -> None:
        mocked_migration_needed.return_value = True
        state = create_state(leader=True, relations=[peer_relation_ready])
        with (
            patch("charm.NOOP_CONDITIONS", new=[Mock(return_value=True)]),
            patch("charm.EVENT_DEFER_CONDITIONS", new=[Mock(return_value=True)]),
        ):
            context.run(context.on.config_changed(), state)

        # Leader should run migration
        mocked_cli.assert_called_once()
        # And should plan after migration
        mocked_pebble_service.return_value.plan.assert_called_once()

    def test_when_pebble_plan_failed(
        self,
        context: Context,
        peer_relation: PeerRelation,
        kratos_info_relation_ready: Relation,
        hydra_endpoint_relation_ready: Relation,
        oauth_relation_ready: Relation,
        openfga_relation_ready: Relation,
        ingress_relation_ready: Relation,
        pg_database_relation_ready: Relation,
        ca_cert_relation_ready: Relation,
        smtp_relation: Relation,
        mocked_oauth_get_provider: MagicMock,
    ) -> None:
        state = create_state(
            relations=[
                peer_relation,
                kratos_info_relation_ready,
                hydra_endpoint_relation_ready,
                oauth_relation_ready,
                openfga_relation_ready,
                ingress_relation_ready,
                pg_database_relation_ready,
                ca_cert_relation_ready,
                smtp_relation,
            ]
        )
        with (
            patch(
                "charm.IdentityPlatformAdminUIOperatorCharm._pebble_layer",
                new_callable=PropertyMock,
            ),
            patch("charm.PebbleService.plan", side_effect=PebbleServiceError),
            patch("charm.NOOP_CONDITIONS", new=[Mock(return_value=True)]),
            patch("charm.EVENT_DEFER_CONDITIONS", new=[Mock(return_value=True)]),
        ):
            out = context.run(context.on.config_changed(), state)

        assert isinstance(out.unit_status, BlockedStatus)
