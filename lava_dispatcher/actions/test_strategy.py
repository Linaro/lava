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
    from lava_dispatcher.action import Action
    from lava_dispatcher.job import Job


class LavaTestStrategy(BaseStrategy):
    section = "test"
    name = "base-test"

    @classmethod
    def check_subclass(cls, device, parameters) -> None:
        # No checks
        ...

    @classmethod
    def action(cls, job: Job, parameters) -> Action:
        raise NotImplementedError(f"action() not implemented in {cls.__name__}")

    @classmethod
    def needs_deployment_data(cls, parameters) -> bool:
        raise NotImplementedError(
            f"needs_deployment_data() not implemented in {cls.__name__}"
        )

    @classmethod
    def needs_overlay(cls, parameters) -> bool:
        raise NotImplementedError(f"needs_overlay() not implemented in {cls.__name__}")

    @classmethod
    def has_shell(cls, parameters) -> bool:
        raise NotImplementedError(f"has_shell() not implemented in {cls.__name__}")


class DockerTest(LavaTestStrategy):
    """
    DockerTest Strategy object
    """

    priority = 10

    @classmethod
    def action(cls, job: Job, parameters) -> Action:
        from lava_dispatcher.actions.test.docker import DockerTestAction

        return DockerTestAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "definition" in parameters or "definitions" in parameters:
            if "docker" in parameters:
                return True, "accepted"
        return False, "docker or definition(s) not in parameters"

    @classmethod
    def needs_deployment_data(cls, parameters) -> bool:
        return False

    @classmethod
    def needs_overlay(cls, parameters) -> bool:
        return True

    @classmethod
    def has_shell(cls, parameters) -> bool:
        return True


@nottest
class TestInteractive(LavaTestStrategy):
    """
    TestInteractive Strategy object
    """

    @classmethod
    def action(cls, job: Job, parameters) -> Action:
        from lava_dispatcher.actions.test.interactive import TestInteractiveRetry

        return TestInteractiveRetry(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        required_parms = ["name", "prompts", "script"]
        if "interactive" in parameters:
            for script in parameters["interactive"]:
                if not all([x for x in required_parms if x in script]):
                    return (
                        False,
                        "missing a required parameter from %s" % required_parms,
                    )
            return True, "accepted"
        return False, '"interactive" not in parameters'

    @classmethod
    def needs_deployment_data(cls, parameters) -> bool:
        return False

    @classmethod
    def needs_overlay(cls, parameters) -> bool:
        return False

    @classmethod
    def has_shell(cls, parameters) -> bool:
        return False


@nottest
class TestMonitor(LavaTestStrategy):
    """
    LavaTestMonitor Strategy object
    """

    @classmethod
    def action(cls, job: Job, parameters) -> Action:
        from lava_dispatcher.actions.test.monitor import TestMonitorRetry

        return TestMonitorRetry(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        # TODO: Add configurable timeouts
        required_parms = ["name", "start", "end", "pattern"]
        if "monitors" in parameters:
            for monitor in parameters["monitors"]:
                for param in required_parms:
                    if param not in monitor:
                        return (False, "missing required parameter '%s'" % param)
            return True, "accepted"
        return False, '"monitors" not in parameters'

    @classmethod
    def needs_deployment_data(cls, parameters) -> bool:
        return False

    @classmethod
    def needs_overlay(cls, parameters) -> bool:
        return False

    @classmethod
    def has_shell(cls, parameters) -> bool:
        return False


class MultinodeTestShell(LavaTestStrategy):
    """
    LavaTestShell Strategy object for Multinode
    """

    # higher priority than the plain TestShell
    priority = 2

    @classmethod
    def action(cls, job: Job, parameters) -> Action:
        if "monitors" in parameters:
            return TestMonitor.action(job, parameters)
        if "interactive" in parameters:
            return TestInteractive.action(job, parameters)

        from lava_dispatcher.actions.test.multinode import MultinodeTestAction

        return MultinodeTestAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        # Avoid importing MultinodeProtocol
        multinode_protocol_name = "lava-multinode"

        if "role" in parameters:
            if multinode_protocol_name in parameters:
                if "target_group" in parameters[multinode_protocol_name]:
                    return True, "accepted"
                else:
                    return (
                        False,
                        '"target_group" was not in parameters for %s'
                        % multinode_protocol_name,
                    )
            else:
                return False, "%s was not in parameters" % multinode_protocol_name
        return False, '"role" not in parameters'

    @staticmethod
    def _get_subaction_class(parameters) -> type[LavaTestStrategy]:
        if "monitors" in parameters:
            return TestMonitor
        if "interactive" in parameters:
            return TestInteractive
        return TestShell

    @classmethod
    def needs_deployment_data(cls, parameters) -> bool:
        """Some, not all, deployments will want deployment_data"""
        return cls._get_subaction_class(parameters).needs_deployment_data(parameters)

    @classmethod
    def needs_overlay(cls, parameters) -> bool:
        return cls._get_subaction_class(parameters).needs_overlay(parameters)

    @classmethod
    def has_shell(cls, parameters) -> bool:
        return cls._get_subaction_class(parameters).has_shell(parameters)


class TestShell(LavaTestStrategy):
    """
    LavaTestShell Strategy object
    """

    @classmethod
    def action(cls, job: Job, parameters) -> Action:
        from lava_dispatcher.actions.test.shell import TestShellRetry

        return TestShellRetry(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "definitions" in parameters:
            return True, "accepted"
        return False, '"definitions" not in parameters'

    @classmethod
    def needs_deployment_data(cls, parameters):
        """Some, not all, deployments will want deployment_data"""
        return True

    @classmethod
    def needs_overlay(cls, parameters):
        return True

    @classmethod
    def has_shell(cls, parameters):
        return True
