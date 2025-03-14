# Changelog

## [1.0.1](https://github.com/canonical/identity-platform-admin-ui-operator/compare/v1.0.0...v1.0.1) (2025-03-14)


### Bug Fixes

* enforce ops to be &gt; 2.18 ([38be1fa](https://github.com/canonical/identity-platform-admin-ui-operator/commit/38be1fa345bf830c8ecc1506eb723bdd32775a6a))

## 1.0.0 (2025-02-17)


### Features

* add oathkeeper-related env variables ([3f46429](https://github.com/canonical/identity-platform-admin-ui-operator/commit/3f4642973cb98b18bbd7b922a31f7efcc402cbe6))
* add observability rules ([4858055](https://github.com/canonical/identity-platform-admin-ui-operator/commit/485805538a185c2ea192b52124c4a90bb88af9af))
* add the create-identity action ([a60ee1c](https://github.com/canonical/identity-platform-admin-ui-operator/commit/a60ee1cd6f0c8b706b62d8b888ea888979934558))
* add the smtp integration ([3110c44](https://github.com/canonical/identity-platform-admin-ui-operator/commit/3110c44c2b9e88d7da69f613f1ffc9a1827f82a7))
* demo charm for admin ui ([52f3bd6](https://github.com/canonical/identity-platform-admin-ui-operator/commit/52f3bd6e32baa6e8c4d47b98e26fa8ec44de61b8))
* drop LOG_FILE support ([e5952c7](https://github.com/canonical/identity-platform-admin-ui-operator/commit/e5952c74f367d41dbc641137a54660c6c64c3d7b))
* first commit with README, CODEOWNERS, CONTRIBUTING.md and license ([64a3272](https://github.com/canonical/identity-platform-admin-ui-operator/commit/64a3272467c783cc6ec421b2ca4a53c8b2f9bff1))
* integrate with kratos and oathkeeper -info ([c7c331a](https://github.com/canonical/identity-platform-admin-ui-operator/commit/c7c331afe9f48cb1f43d59d16059ce4986449a2a))
* integrate with openfga ([da18e20](https://github.com/canonical/identity-platform-admin-ui-operator/commit/da18e208673e78afcab634b52a7071721c34e941))
* set blocked status if kratos or hydra is missing ([504a246](https://github.com/canonical/identity-platform-admin-ui-operator/commit/504a2468e6a8d78c40a8bb3a7f2f1717379b0177))
* switch to v1 cert transfer requirer ([99793bd](https://github.com/canonical/identity-platform-admin-ui-operator/commit/99793bd523229cb17713fb0543154289ad27807d))
* upgrade to v2 tracing ([44e18e6](https://github.com/canonical/identity-platform-admin-ui-operator/commit/44e18e61546ccc5b04d2e331c02bd927f8545a4d))
* use CollectStatusEvent API to centrally manage charm status ([#15](https://github.com/canonical/identity-platform-admin-ui-operator/issues/15)) ([1c4574a](https://github.com/canonical/identity-platform-admin-ui-operator/commit/1c4574a48e1f7b88a59d8298ecb2b4d92900f823))
* use tracing v2 ([ce0cb5d](https://github.com/canonical/identity-platform-admin-ui-operator/commit/ce0cb5dec9343a46a1885db0dc211b1ec47d67be))


### Bug Fixes

* add recieve-ca-cert relation ([8867043](https://github.com/canonical/identity-platform-admin-ui-operator/commit/8867043607197c63d159ad0d68be63671ab68735))
* add the cert transfer integration to integration test ([c8595b3](https://github.com/canonical/identity-platform-admin-ui-operator/commit/c8595b338c71b3e716f77617c06c68c091c2de20))
* add the handler for handling kratos and hydra integration removal ([edec476](https://github.com/canonical/identity-platform-admin-ui-operator/commit/edec4766ef95bbf5d854aeb10cd481822ffaa612))
* check if store_id exists ([61996d7](https://github.com/canonical/identity-platform-admin-ui-operator/commit/61996d7c6cb2411a34a7fe146e0cfa2289916047))
* drop v0 cert-transfer lib in favour of v1 ([2a4a4a5](https://github.com/canonical/identity-platform-admin-ui-operator/commit/2a4a4a522e5f761fc93dca04f6b482cba6dfe394))
* fix test_when_a_condition_failed test ([59a7798](https://github.com/canonical/identity-platform-admin-ui-operator/commit/59a77988be49d13f736cfbed1995705e96e1efc2))
* handle multiple cert transfer integrations ([54ad6af](https://github.com/canonical/identity-platform-admin-ui-operator/commit/54ad6afc44f2df7e284d1066146aff4326f4713e))
* implement cert trust logic ([0d9a71f](https://github.com/canonical/identity-platform-admin-ui-operator/commit/0d9a71fd7be5cbf76a16f5eb909b12bf3c710c9d))
* introduce oauth integration ([30d206c](https://github.com/canonical/identity-platform-admin-ui-operator/commit/30d206cb27a6d3d087068a17c0bcfbd4d137ad95))
* make ingress required for oauth ([380b6db](https://github.com/canonical/identity-platform-admin-ui-operator/commit/380b6db657db67ec895de4e67893d4f48660edd3))
* move pebble.plan to the holistic handler ([e81a5e4](https://github.com/canonical/identity-platform-admin-ui-operator/commit/e81a5e4761d82e3f325f0f3f0160b6c52c560816))
* notify non-leaders when peer relation changes ([eafdda8](https://github.com/canonical/identity-platform-admin-ui-operator/commit/eafdda8a4a3bde5c6b2895acd950dd60893eaf59))
* raise error if kratos data is None ([81a0c13](https://github.com/canonical/identity-platform-admin-ui-operator/commit/81a0c13282643db2a0ecee5c8525cdd62366ee00))
* remove the unnecessary dependencies ([7648f81](https://github.com/canonical/identity-platform-admin-ui-operator/commit/7648f8100bc4fdf8153b2c23bba2688cdca2ed10))
* require openfga data to start the service ([16dfc5d](https://github.com/canonical/identity-platform-admin-ui-operator/commit/16dfc5d3e6b5c4535353da9a658c948118817cc7))
* set workload version ([90d5e89](https://github.com/canonical/identity-platform-admin-ui-operator/commit/90d5e89e4ed7abcb75b153ffc3323c4adf6d6b9c))
* update oauth integration ([220f775](https://github.com/canonical/identity-platform-admin-ui-operator/commit/220f77585c2af6a89009959c0856c542445e0d50))
* update start command ([033c0c1](https://github.com/canonical/identity-platform-admin-ui-operator/commit/033c0c1f4884aff2cb3af7f34f80f7102293bcec))
* uppercase the logging level ([e61bc84](https://github.com/canonical/identity-platform-admin-ui-operator/commit/e61bc84960563320881d86a17aa72abd29d8ea46))
* use the service_context for commands that needs the pebble service's context ([a93049d](https://github.com/canonical/identity-platform-admin-ui-operator/commit/a93049d626f96f97c295833573875e7388263edd))
