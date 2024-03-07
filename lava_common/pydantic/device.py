# Copyright (C) 2024 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel, Field

from .timeout import Timeout


class CharacterDelays(BaseModel):
    boot: Optional[int] = None
    test: Optional[int] = None


class Connection(BaseModel):
    connect: str
    tags: Optional[list[str]] = None


class Users(BaseModel):
    do: str
    undo: Optional[str] = None


class Commands(BaseModel):
    connect: Optional[str] = None
    connections: Optional[dict[str, Connection]] = None
    hard_reset: Optional[Union[str, list[str]]] = None
    soft_reboot: Optional[Union[str, list[str]]] = None
    power_on: Optional[Union[str, list[str]]] = None
    pre_power_command: Optional[Union[str, list[str]]] = None
    pre_os_command: Optional[Union[str, list[str]]] = None
    users: Optional[dict[str, Users]] = None


class Sata(BaseModel):
    uuid: str
    device_id: int
    uboot_interface: str
    grub_interface: str
    boot_part: int


class Sd(BaseModel):
    uuid: str
    device_id: int


class Usb(BaseModel):
    uuid: str
    device_id: int


class Image(BaseModel):
    kernel: str
    ramdisk: str
    dtb: str


class Media(BaseModel):
    sata: Optional[dict[str, Sata]] = None
    sd: Optional[dict[str, Sd]] = None
    usb: Optional[dict[str, Usb]] = None


class Parameters(BaseModel):
    interfaces: Optional[dict[str, Any]] = None
    media: Optional[Media] = None
    image: Optional[Image] = None
    booti: Optional[Image] = None
    uimage: Optional[Image] = None
    bootm: Optional[Image] = None
    zimage: Optional[Image] = None
    bootz: Optional[Image] = None


class Deploy(BaseModel):
    methods: dict[str, Any]
    connections: Optional[dict[str, Any]] = None
    parameters: Optional[dict[str, Any]] = None


class Boot(BaseModel):
    connections: dict[str, Any]
    methods: dict[str, Any]


class Actions(BaseModel):
    deploy: Deploy
    boot: Boot


class Timeouts(BaseModel):
    actions: dict[str, Timeout]
    connections: dict[str, Timeout]


class Device(BaseModel):
    character_delays: Optional[CharacterDelays] = None
    constants: dict[str, Any]
    test: Optional[int] = None
    commands: Optional[Commands] = None
    adb_serial_number: Optional[str] = None
    fastboot_serial_number: Optional[str] = None
    fastboot_options: Optional[list[str]] = None
    fastboot_via_uboot: Optional[bool] = None
    device_info: Optional[list[dict[str, Any]]] = None
    static_info: Optional[list[dict[str, Any]]] = None
    storage_info: Optional[list[dict[str, Any]]] = None
    environment: Optional[dict[str, Any]] = None
    flash_cmds_order: Optional[list[str]] = None
    board_id: Optional[str] = None
    usb_vendor_id: Optional[str] = None
    usb_product_id: Optional[str] = None
    usb_sleep: Optional[int] = None
    usb_filesystem_label: Optional[str] = None
    usb_serial_driver: Optional[str] = None
    timeouts: Timeouts
    available_architectures: Optional[list[str]] = None
    power_state: bool = False
    dynamic_data: dict[Any, Any] = Field(default_factory=dict)
