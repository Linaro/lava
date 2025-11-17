#!/usr/bin/python3
#
# Copyright (C) 2025 Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Type

import jinja2
from dacite import Config as DaciteConfig
from dacite import WrongTypeError, from_dict
from yaml import safe_load as yaml_safe_load

BASEDIR = Path(__file__).resolve().parent

logger = logging.getLogger(__name__)


#####################
# labgrid resources #
#####################
@dataclass(frozen=True)
class DockerDaemon:
    docker_daemon_url: str


##################
# labgrid drivers #
##################
@dataclass(frozen=True)
class ExternalPowerDriver:
    cmd_off: str
    cmd_on: str
    delay: float = 2.0
    cmd_cycle: str | None = None


@dataclass(frozen=True)
class ExternalConsoleDriver:
    cmd: str
    txdelay: float = 0.0


@dataclass(frozen=True)
class UBootDriver:
    prompt: str = ""
    bootstring: str = "Linux version \\d"
    boot_timeout: int = 30
    login_timeout: int = 30


@dataclass(frozen=True)
class ShellDriver:
    prompt: str
    login_prompt: str
    username: str
    password: str | None = None
    keyfile: str | None = None
    login_timeout: int = 60
    await_login_timeout: int = 2
    console_ready: str | None = None
    post_login_settle_time: int = 0


@dataclass(frozen=True)
class DockerDriver:
    image_uri: str
    pull: str = "always"
    volumes: list[str] | None = None


@dataclass(frozen=True)
class SSHDriver:
    keyfile: str | None = None


######################
# labgrid strategies #
######################
@dataclass(frozen=True)
class UBootStrategy:
    ...


@dataclass(frozen=True)
class DockerStrategy:
    ...


@dataclass(frozen=True)
class ShellStrategy:
    ...


###############
# labgrid env #
###############
@dataclass(frozen=True)
class Resources:
    docker_daemon: DockerDaemon | None = None


@dataclass(frozen=True)
class Drivers:
    external_power_driver: ExternalPowerDriver | None = None
    external_console_driver: ExternalConsoleDriver | None = None
    uboot_driver: UBootDriver | None = None
    shell_driver: ShellDriver | None = None
    docker_driver: DockerDriver | None = None
    ssh_driver: SSHDriver | None = None
    shell_strategy: ShellStrategy | None = None
    uboot_strategy: UBootStrategy | None = None
    docker_strategy: DockerStrategy | None = None


@dataclass(frozen=True)
class Target:
    drivers: Drivers
    resources: Resources | None = None


@dataclass(frozen=True)
class LgConfig:
    targets: dict[str, Target]
    images: dict[str, str] | None = None

    @staticmethod
    def camel_to_snake(name: str) -> str:
        # e.g. ExternalPowerDriver -> External_Power_Driver
        s1 = re.sub(r"([a-z])([A-Z])", r"\1_\2", name)

        # e.g.
        # UBootDriver -> UBoot_Driver
        # USBSerialPort -> USB_Serial_Port
        s2 = re.sub(r"([A-Z]{2,})([A-Z][a-z])", r"\1_\2", s1)

        return s2.lower()

    @classmethod
    def load(cls, lg_env: Path) -> LgConfig:
        raw_lg_env = yaml_safe_load(lg_env.read_text())

        for key in raw_lg_env:
            if key not in cls.__dataclass_fields__:
                logger.warning(f"Top-level key {key!r} is not supported yet!")

        dataclass_map: dict[str, Type[Resources | Drivers]] = {
            "resources": Resources,
            "drivers": Drivers,
        }

        # Convert target resource/driver classname to dataclass attribute name.
        for _, conf in raw_lg_env.get("targets", {}).items():
            for section in ["resources", "drivers"]:
                if section in conf:
                    # Labgrid supports both list and dict for resources/drivers.
                    if isinstance(conf[section], list):
                        # Convert list to dict.
                        section_dict = {}
                        for item in conf[section]:
                            section_dict.update(item)
                        conf[section] = section_dict

                    if isinstance(conf[section], dict):
                        # Creates a copy of the keys.
                        for key in list(conf[section].keys()):
                            new_key = cls.camel_to_snake(key)
                            if (
                                new_key
                                not in dataclass_map[section].__dataclass_fields__
                            ):
                                logger.warning(
                                    f"'{section}.{key}' is not supported yet!"
                                )
                                continue
                            conf[section][new_key] = conf[section].pop(key)
                    else:
                        logger.warning(f"'{section}' should be a list or dict")
                        raise SystemExit(1)

        try:
            lg_config = from_dict(
                data_class=cls,
                data=raw_lg_env,
                config=DaciteConfig(
                    # Force value type
                    check_types=True,
                    # Allow missing key
                    strict=False,
                ),
            )
            return lg_config
        except WrongTypeError as exc:
            logger.error(str(exc))
            raise SystemExit(1)


class LavaConfig:
    def __init__(self, output_dir: Path, device_type: str | None, lg_config: LgConfig):
        self.targets: dict[str, Any] = lg_config.targets
        # TODO(Chase): extend job template for image deployment when there is a use case.
        if lg_config.images:
            self.images: dict[str, str] | None = lg_config.images
        self.device_template: Path = BASEDIR / "templates/device.jinja2"
        self.job_template: Path = BASEDIR / "templates/job.jinja2"
        self.output_dir: Path = output_dir
        self.device_type: str | None = device_type

    def render_device(self, name: str, target: Target) -> None:
        template_dirs = [
            BASEDIR / "templates",
            BASEDIR / "../../etc/dispatcher-config/device-types",
        ]

        env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dirs))
        template = env.get_template("device.jinja2")
        try:
            data = template.render(
                device_type=self.device_type,
                target=target,
            )
        except jinja2.exceptions.TemplateNotFound as exc:
            logger.error(f"Device template not found: {exc}")
            raise SystemExit(1)
        except jinja2.exceptions.UndefinedError as exc:
            logger.error(f"Device template undefined attribute error: {exc}")
            raise SystemExit(1)
        except Exception as exc:
            logger.error(f"Device template rendering error: {exc}")
            raise SystemExit(1)
        # Remove empty lines.
        clean_data = "\n".join([line for line in data.splitlines() if line.strip()])

        output_file = self.output_dir / f"device.yaml"
        output_file.write_text(clean_data)
        logger.info(f"Generated LAVA device config: {output_file}")

    def render_job(self, name: str, target: Target) -> None:
        template_str = self.job_template.read_text()
        template = jinja2.Template(template_str)
        try:
            data = template.render(
                name=name,
                device_type=self.device_type,
                target=target,
            )
        except jinja2.exceptions.UndefinedError as exc:
            logger.error(f"Job template undefined attribute error: {exc}")
            raise SystemExit(1)
        except Exception as exc:
            logger.error(f"Job template rendering error: {exc}")
            raise SystemExit(1)
        # Remove empty lines.
        clean_data = "\n".join([line for line in data.splitlines() if line.strip()])

        output_file = self.output_dir / f"job.yaml"
        output_file.write_text(clean_data)
        logger.info(f"Generated LAVA job config: {output_file}")

    def convert(self) -> None:
        for name, target in self.targets.items():
            self.render_device(name, target)
            self.render_job(name, target)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert labgrid config to LAVA configs"
    )

    parser.add_argument(
        "-l",
        "--lg-env",
        type=Path,
        required=True,
        help="labgrid environment config file",
    )
    parser.add_argument(
        "-d",
        "--device-type",
        type=str,
        default=None,
        help="LAVA device type name",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for LAVA configs",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    return parser.parse_args()


##############
# Entrypoint #
##############
def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not args.lg_env.exists():
        logger.error(f"{args.lg_env} not exist")
        raise SystemExit(1)
    lg_config = LgConfig.load(args.lg_env)

    if not args.output_dir.exists():
        args.output_dir.mkdir(parents=True, exist_ok=True)

    lava_config = LavaConfig(args.output_dir, args.device_type, lg_config)
    lava_config.convert()


if __name__ == "__main__":
    main()
