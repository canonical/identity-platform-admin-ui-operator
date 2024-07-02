# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import ConfigData

from env_vars import EnvVars


class CharmConfig:
    def __init__(self, config: ConfigData) -> None:
        self._config = config

    def to_env_vars(self) -> EnvVars:
        log_level = self._config["log_level"]
        return {
            "LOG_LEVEL": log_level,
            "DEBUG": "DEBUG" == log_level,
        }
