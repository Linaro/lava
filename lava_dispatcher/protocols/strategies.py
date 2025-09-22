# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from lava_common.constants import MULTINODE_PROTOCOL

if TYPE_CHECKING:
    from typing import Any

    from ..connection import Protocol


class ProtocolStrategy:
    @classmethod
    def select_all(cls, parameters: dict[str, Any]) -> list[tuple[type[Protocol], int]]:
        """
        Multiple protocols can apply to the same job, each with their own parameters.
        Jobs may have zero or more protocols selected.
        """
        candidates = (
            strategy.get_protocol_class()
            for strategy in cls.__subclasses__()
            if strategy.accepts(parameters)
        )
        return [(c, c.level) for c in candidates]

    @classmethod
    def accepts(cls, parameters: dict[str, Any]) -> bool:
        raise NotImplementedError

    @classmethod
    def get_protocol_class(cls) -> type[Protocol]:
        raise NotImplementedError


class LxcStrategy(ProtocolStrategy):
    @classmethod
    def accepts(cls, parameters: dict[str, Any]) -> bool:
        if "protocols" not in parameters:
            return False
        if "lava-lxc" not in parameters["protocols"]:
            return False
        if "name" not in parameters["protocols"]["lava-lxc"]:
            return False
        if "distribution" not in parameters["protocols"]["lava-lxc"]:
            return False
        if "release" not in parameters["protocols"]["lava-lxc"]:
            return False
        return True

    @classmethod
    def get_protocol_class(cls) -> type[Protocol]:
        from lava_dispatcher.protocols.lxc import LxcProtocol

        return LxcProtocol


class MultinodeStrategy(ProtocolStrategy):
    @classmethod
    def accepts(cls, parameters: dict[str, Any]) -> bool:
        if "protocols" not in parameters:
            return False
        if "lava-multinode" not in parameters["protocols"]:
            return False
        if "target_group" in parameters["protocols"][MULTINODE_PROTOCOL]:
            return True
        return False

    @classmethod
    def get_protocol_class(cls) -> type[Protocol]:
        from lava_dispatcher.protocols.multinode import MultinodeProtocol

        return MultinodeProtocol


class VlandStrategy(ProtocolStrategy):
    @classmethod
    def accepts(cls, parameters: dict[str, Any]) -> bool:
        if "protocols" not in parameters:
            return False
        if "lava-multinode" not in parameters["protocols"]:
            return False
        if "target_group" not in parameters["protocols"][MULTINODE_PROTOCOL]:
            return False
        if "lava-vland" not in parameters["protocols"]:
            return False
        return True

    @classmethod
    def get_protocol_class(cls) -> type[Protocol]:
        from lava_dispatcher.protocols.vland import VlandProtocol

        return VlandProtocol


class XnbdStrategy(ProtocolStrategy):
    @classmethod
    def accepts(cls, parameters: dict[str, Any]) -> bool:
        if "protocols" not in parameters:
            return False
        if "lava-xnbd" not in parameters["protocols"]:
            return False
        return True

    @classmethod
    def get_protocol_class(cls) -> type[Protocol]:
        from lava_dispatcher.protocols.xnbd import XnbdProtocol

        return XnbdProtocol
