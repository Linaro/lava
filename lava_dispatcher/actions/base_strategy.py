# Copyright (C) 2024 Linaro Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from lava_common.exceptions import JobError

if TYPE_CHECKING:
    from typing import ClassVar, TypeVar

    from lava_dispatcher.action import Action
    from lava_dispatcher.job import Job

    TStrategy = TypeVar("TStrategy", bound="BaseStrategy")


class BaseStrategy:
    priority: ClassVar[int] = -1
    section: ClassVar[str] = "base"
    name: ClassVar[str] = "base"

    @classmethod
    def action(cls, job: Job) -> Action:
        raise NotImplementedError(f"action() not implemented in {cls.__name__}")

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        """Must be implemented by subclasses."""
        raise NotImplementedError(f"accepts() not implemented in {cls.__name__}")

    @classmethod
    def check_subclass(cls, device, parameters) -> None:
        raise NotImplementedError(f"check_subclass() not implemented in {cls.__name__}")

    @classmethod
    def select(cls: type[TStrategy], device, parameters) -> type[TStrategy]:
        cls.check_subclass(device, parameters)
        candidates = cls.__subclasses__()
        replies: dict[str, str] = {}
        willing: list[type[TStrategy]] = []

        for c in candidates:
            is_accepted, message = c.accepts(device, parameters)

            if is_accepted:
                willing.append(c)
            else:
                replies[c.name] = message

        if not willing:
            replies_string = "\n".join(
                f"{name}: {reply}" for name, reply in replies.items()
            )
            raise JobError(
                f"None of the {cls.name.capitalize()} strategies accepted "
                f"your deployment parameters, reasons given:\n{replies_string}"
            )

        willing.sort(key=lambda x: x.priority, reverse=True)
        return willing[0]
