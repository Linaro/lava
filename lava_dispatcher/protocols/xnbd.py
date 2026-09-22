# Copyright (C) 2017 The Linux Foundation
#
# Author: Jan-Simon Moeller <jsmoeller@linuxfoundation.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

import pexpect

from lava_common.constants import XNBD_SYSTEM_TIMEOUT
from lava_common.exceptions import JobError, LAVABug, TestError
from lava_common.timeout import Timeout
from lava_dispatcher.connection import Protocol
from lava_dispatcher.shell import ShellSession
from lava_dispatcher.utils.network import dispatcher_ip, get_free_port

if TYPE_CHECKING:
    from typing import Any

    from lava_common.log import YAMLLogger
    from lava_dispatcher.action import Action


class XnbdProtocol(Protocol):
    """
    Xnbd protocol (nbd-server teardown)
    """

    name = "lava-xnbd"

    def __init__(self, parameters: dict[str, Any], job_id: str, job_logger: YAMLLogger):
        super().__init__(parameters, job_id, job_logger)
        # timeout in utils.constants, default 10000
        self.system_timeout = Timeout("system", None, duration=XNBD_SYSTEM_TIMEOUT)
        self.parameters = parameters
        self.ports: list[int] = []

    @classmethod
    def accepts(cls, parameters: dict[str, Any]) -> bool:
        if "protocols" not in parameters:
            return False
        if "lava-xnbd" not in parameters["protocols"]:
            return False
        return True

    def collate(
        self,
        reply: str | dict[str, Any] | None,
        params: dict[str, Any],
    ) -> tuple[str, Any] | None:
        """
        Merge the reply to the protocol call into the request params.
        Arguments: reply - the dict returned by the protocol API call
                   params - the request dict to merge the reply into
        No namespace data is produced, so always returns None.
        """
        if isinstance(reply, dict):
            params.update(reply)
        return None

    def set_up(self) -> None:
        """
        Called from the job at the start of the run step.
        """

        if "port" not in self.parameters["protocols"]["lava-xnbd"]:
            self.errors_add(
                "No port set in parameters for lava-xnbd protocol!\nE.g.:\n protocols:\n  lava-xnbd:\n    port: auto \n"
            )

    def __call__(self, *args: Any, **kwargs: Any) -> Any | None:
        action: Action | None = kwargs.get("action")
        if action is None:
            raise LAVABug("Expected 'action' key to contain Action object")
        self.logger.debug("[%s] Checking protocol data for %s", action.name, self.name)
        try:
            return self._api_select(args, action=action)
        except (ValueError, TypeError) as exc:
            raise JobError(f"Invalid call to {self.name} {exc}")

    def _api_select(self, data: Any | None, action: Action | None = None) -> Any | None:
        if action is None:
            raise LAVABug("Expected Action object")
        if not data:
            raise TestError("Protocol called without any data")
        for item in data:
            if "request" not in item:
                raise JobError("Bad API call over protocol - missing request")
            if "set_port" in item["request"]:
                return self.set_port(action=action)
            else:
                raise JobError("Unrecognised API call in request.")
        return None

    def set_port(self, action: Action) -> dict[str, int]:
        msg = {"data": {"nbd_server_port": 10809}}
        nbd_port = self.parameters["protocols"]["lava-xnbd"]["port"]
        if nbd_port == "auto":
            self.logger.debug("Get a port from pool")
            nbd_port = get_free_port(self.parameters["dispatcher"])
        self.ports.append(nbd_port)
        msg["data"]["nbd_server_port"] = nbd_port
        action.set_namespace_data(
            "nbd-deploy",
            label="nbd",
            key="nbd_server_port",
            value=nbd_port,
            parameters=action.parameters,
        )
        nbd_ip = dispatcher_ip(self.parameters["dispatcher"])
        action.set_namespace_data(
            "nbd-deploy",
            label="nbd",
            key="nbd_server_ip",
            value=nbd_ip,
            parameters=action.parameters,
        )
        self.logger.debug("Set_port %d", nbd_port)
        return msg["data"]

    def finalise_protocol(self, device: dict[str, Any] | None = None) -> None:
        """Called by Finalize action to power down and clean up the assigned
        device.
        """
        # shutdown nbd-server for the given device/job based in the port-number used
        try:
            self.logger.debug("%s cleanup", self.name)
            for port in self.ports:
                self.logger.debug("clean NBD port %s", port)
                nbd_cmd = "pkill -f nbd-server.*%s" % (port)
                shell = ShellSession(
                    f"{nbd_cmd}\n", self.system_timeout, logger=self.logger
                )
                with shell._expect_exc_wrapper():
                    shell.raw_connection.expect(pexpect.EOF)
        except Exception as e:
            self.logger.debug(str(e))
            self.logger.debug("xnbd-finalize-protocol failed, but continuing anyway.")
