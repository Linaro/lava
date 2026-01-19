# Copyright (C) 2024 Linaro Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from lava_common.decorators import nottest

from .base_strategy import BaseStrategy

if TYPE_CHECKING:
    from typing import Any

    from lava_dispatcher.action import Action
    from lava_dispatcher.job import Job


class LavaTestStrategy(BaseStrategy):
    section = "test"
    name = "base-test"

    @classmethod
    def check_subclass(cls, device: dict[str, Any], parameters: dict[str, Any]) -> None:
        # No checks
        ...

    @classmethod
    def action(  # type: ignore[override]
        cls, job: Job, parameters: dict[str, Any]
    ) -> Action:
        raise NotImplementedError(f"action() not implemented in {cls.__name__}")

    @classmethod
    def needs_deployment_data(cls, parameters: dict[str, Any]) -> bool:
        raise NotImplementedError(
            f"needs_deployment_data() not implemented in {cls.__name__}"
        )

    @classmethod
    def needs_overlay(cls, parameters: dict[str, Any]) -> bool:
        raise NotImplementedError(f"needs_overlay() not implemented in {cls.__name__}")

    @classmethod
    def has_shell(cls, parameters: dict[str, Any]) -> bool:
        raise NotImplementedError(f"has_shell() not implemented in {cls.__name__}")

    @classmethod
    def needs_character_delay(cls, parameters: dict[str, Any]) -> bool:
        raise NotImplementedError(
            f"needs_character_delay() not implemented in {cls.__name__}"
        )


class DockerTest(LavaTestStrategy):
    """
    DockerTest Strategy object
    """

    priority = 10

    @classmethod
    def action(  # type: ignore[override]
        cls, job: Job, parameters: dict[str, Any]
    ) -> Action:
        from lava_dispatcher.actions.test.docker import DockerTestAction

        return DockerTestAction(job)

    @classmethod
    def accepts(
        cls, device: dict[str, Any], parameters: dict[str, Any]
    ) -> tuple[bool, str]:
        if "definition" in parameters or "definitions" in parameters:
            if "docker" in parameters:
                return True, "accepted"
        return False, "docker or definition(s) not in parameters"

    @classmethod
    def needs_deployment_data(cls, parameters: dict[str, Any]) -> bool:
        return False

    @classmethod
    def needs_overlay(cls, parameters: dict[str, Any]) -> bool:
        return True

    @classmethod
    def has_shell(cls, parameters: dict[str, Any]) -> bool:
        return False

    @classmethod
    def needs_character_delay(cls, parameters: dict[str, Any]) -> bool:
        return False


@nottest
class TestInteractive(LavaTestStrategy):
    """
    TestInteractive Strategy object
    """

    @classmethod
    def action(  # type: ignore[override]
        cls, job: Job, parameters: dict[str, Any]
    ) -> Action:
        from lava_dispatcher.actions.test.interactive import TestInteractiveRetry

        return TestInteractiveRetry(job)

    @classmethod
    def accepts(
        cls, device: dict[str, Any], parameters: dict[str, Any]
    ) -> tuple[bool, str]:
        if "interactive" not in parameters:
            return False, '"interactive" not in parameters'

        required_parms = {"name", "prompts", "script"}
        for script in parameters["interactive"]:
            missing = required_parms - script.keys()
            if missing:
                return False, f"missing required parameters {sorted(missing)}"

        return True, "accepted"

    @classmethod
    def needs_deployment_data(cls, parameters: dict[str, Any]) -> bool:
        return False

    @classmethod
    def needs_overlay(cls, parameters: dict[str, Any]) -> bool:
        return False

    @classmethod
    def has_shell(cls, parameters: dict[str, Any]) -> bool:
        return False

    @classmethod
    def needs_character_delay(cls, parameters: dict[str, Any]) -> bool:
        return False


@nottest
class TestMonitor(LavaTestStrategy):
    """
    LavaTestMonitor Strategy object
    """

    @classmethod
    def action(  # type: ignore[override]
        cls, job: Job, parameters: dict[str, Any]
    ) -> Action:
        from lava_dispatcher.actions.test.monitor import TestMonitorRetry

        return TestMonitorRetry(job)

    @classmethod
    def accepts(
        cls, device: dict[str, Any], parameters: dict[str, Any]
    ) -> tuple[bool, str]:
        # TODO: Add configurable timeouts
        if "monitors" not in parameters:
            return False, '"monitors" not in parameters'

        required_parms = {"name", "start", "end", "pattern"}
        for monitor in parameters["monitors"]:
            missing = required_parms - monitor.keys()
            if missing:
                return False, f"missing required parameters {sorted(missing)}"

        return True, "accepted"

    @classmethod
    def needs_deployment_data(cls, parameters: dict[str, Any]) -> bool:
        return False

    @classmethod
    def needs_overlay(cls, parameters: dict[str, Any]) -> bool:
        return False

    @classmethod
    def has_shell(cls, parameters: dict[str, Any]) -> bool:
        return False

    @classmethod
    def needs_character_delay(cls, parameters: dict[str, Any]) -> bool:
        return False


class MultinodeTestShell(LavaTestStrategy):
    """
    LavaTestShell Strategy object for Multinode
    """

    # higher priority than the plain TestShell
    priority = 2

    @classmethod
    def action(  # type: ignore[override]
        cls, job: Job, parameters: dict[str, Any]
    ) -> Action:
        if "monitors" in parameters:
            return TestMonitor.action(job, parameters)
        if "interactive" in parameters:
            return TestInteractive.action(job, parameters)

        from lava_dispatcher.actions.test.multinode import MultinodeTestAction

        return MultinodeTestAction(job)

    @classmethod
    def accepts(
        cls, device: dict[str, Any], parameters: dict[str, Any]
    ) -> tuple[bool, str]:
        # Avoid importing MultinodeProtocol
        multinode_protocol_name = "lava-multinode"

        if "role" not in parameters:
            return False, '"role" not in parameters'
        if multinode_protocol_name not in parameters:
            return False, f"{multinode_protocol_name} was not in parameters"
        if "target_group" not in parameters[multinode_protocol_name]:
            return (
                False,
                f'"target_group" was not in parameters for {multinode_protocol_name}',
            )

        return True, "accepted"

    @staticmethod
    def _get_subaction_class(parameters: dict[str, Any]) -> type[LavaTestStrategy]:
        if "monitors" in parameters:
            return TestMonitor
        if "interactive" in parameters:
            return TestInteractive
        if "docker" in parameters:
            return DockerTest
        return TestShell

    @classmethod
    def needs_deployment_data(cls, parameters: dict[str, Any]) -> bool:
        """Some, not all, deployments will want deployment_data"""
        return cls._get_subaction_class(parameters).needs_deployment_data(parameters)

    @classmethod
    def needs_overlay(cls, parameters: dict[str, Any]) -> bool:
        return cls._get_subaction_class(parameters).needs_overlay(parameters)

    @classmethod
    def has_shell(cls, parameters: dict[str, Any]) -> bool:
        return cls._get_subaction_class(parameters).has_shell(parameters)

    @classmethod
    def needs_character_delay(cls, parameters: dict[str, Any]) -> bool:
        return cls._get_subaction_class(parameters).needs_character_delay(parameters)


class TestShell(LavaTestStrategy):
    """
    LavaTestShell Strategy object
    """

    @classmethod
    def action(  # type: ignore[override]
        cls, job: Job, parameters: dict[str, Any]
    ) -> Action:
        from lava_dispatcher.actions.test.shell import TestShellRetry

        return TestShellRetry(job)

    @classmethod
    def accepts(
        cls, device: dict[str, Any], parameters: dict[str, Any]
    ) -> tuple[bool, str]:
        if "definitions" in parameters:
            return True, "accepted"
        return False, '"definitions" not in parameters'

    @classmethod
    def needs_deployment_data(cls, parameters: dict[str, Any]) -> bool:
        """Some, not all, deployments will want deployment_data"""
        return True

    @classmethod
    def needs_overlay(cls, parameters: dict[str, Any]) -> bool:
        return True

    @classmethod
    def has_shell(cls, parameters: dict[str, Any]) -> bool:
        return True

    @classmethod
    def needs_character_delay(cls, parameters: dict[str, Any]) -> bool:
        return True
