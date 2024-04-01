# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import unittest
from unittest.mock import patch

from lava_dispatcher.actions.boot import (
    BootloaderCommandOverlay,
    BootloaderSecondaryMedia,
)
from lava_dispatcher.actions.boot.grub import GrubMainAction
from lava_dispatcher.actions.boot.u_boot import UBootAction
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.removable import DDAction, MassStorage
from lava_dispatcher.actions.deploy.tftp import TftpAction
from lava_dispatcher.utils.strings import map_kernel_uboot, substitute
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase
from tests.utils import infrastructure_error


class TestRemovable(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()

    def test_device_parameters(self):
        """
        Test that the correct parameters have been set for the device
        """
        cubie = self.factory.load_device_configuration_dict("cubie2")
        self.assertIsNotNone(cubie["parameters"]["media"].get("usb"))
        self.assertIsNotNone(cubie.get("commands"))
        self.assertIsNotNone(cubie.get("actions"))
        self.assertIsNotNone(cubie["actions"].get("deploy"))
        self.assertIsNotNone(cubie["actions"]["deploy"].get("methods"))
        self.assertIn("usb", cubie["actions"]["deploy"]["methods"])
        self.assertIsNotNone(cubie["actions"].get("boot"))
        self.assertIsNotNone(cubie["actions"]["boot"].get("methods"))
        self.assertIn("u-boot", cubie["actions"]["boot"]["methods"])
        u_boot_params = cubie["actions"]["boot"]["methods"]["u-boot"]
        self.assertIn("usb", u_boot_params)
        self.assertIn("commands", u_boot_params["usb"])
        self.assertIn("parameters", u_boot_params)
        self.assertIn("bootloader_prompt", u_boot_params["parameters"])

    def _check_job_parameters(self, job, agent_key):
        action = job.pipeline.actions[3]
        self.assertTrue(action.valid)
        agent = action.parameters[agent_key]["tool"]
        self.assertTrue(
            agent.startswith("/")
        )  # needs to be a full path but on the device, so avoid os.path
        self.assertIn(
            action.parameters["device"], job.device["parameters"]["media"]["usb"]
        )
        mass_storage = action

        self.assertIsNotNone(mass_storage)
        self.assertIn("device", mass_storage.parameters)
        self.assertIn(
            mass_storage.parameters["device"], job.device["parameters"]["media"]["usb"]
        )
        self.assertIsNotNone(
            mass_storage.get_namespace_data(
                action="storage-deploy", label="u-boot", key="device"
            )
        )
        u_boot_params = job.device["actions"]["boot"]["methods"]["u-boot"]
        self.assertEqual(
            mass_storage.get_namespace_data(
                action="uboot-commands", label="bootloader_prompt", key="prompt"
            ),
            u_boot_params["parameters"]["bootloader_prompt"],
        )

    def test_job_parameters(self):
        """
        Test that the job parameters match expected structure
        """
        job_filename = "cubietruck-removable.yaml"
        job = self.factory.create_job(
            "cubie1",
            f"sample_jobs/{job_filename}",
        )
        job.validate()
        self._check_job_parameters(job, "download")
        description_ref = self.pipeline_reference(job_filename, job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

    def test_writer_job_parameters(self):
        """
        Test that the job parameters with a writer tool match expected structure
        """
        job_filename = "cubietruck-removable-with-writer.yaml"
        job = self.factory.create_job(
            "cubie1",
            f"sample_jobs/{job_filename}",
        )
        job.validate()
        self._check_job_parameters(job, "writer")
        description_ref = self.pipeline_reference(job_filename, job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

    def _check_deployment(self, device_name, test_file):
        job = self.factory.create_job(device_name, f"sample_jobs/{test_file}")
        job.validate()
        description_ref = self.pipeline_reference(test_file, job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        self.assertIn("usb", job.device["parameters"]["media"].keys())
        deploy_params = [
            methods
            for methods in job.parameters["actions"]
            if "deploy" in methods.keys()
        ][1]["deploy"]
        self.assertIn("device", deploy_params)
        self.assertIn(deploy_params["device"], job.device["parameters"]["media"]["usb"])
        self.assertIn(
            "uuid", job.device["parameters"]["media"]["usb"][deploy_params["device"]]
        )
        self.assertIn(
            "device_id",
            job.device["parameters"]["media"]["usb"][deploy_params["device"]],
        )
        self.assertNotIn(
            "boot_part",
            job.device["parameters"]["media"]["usb"][deploy_params["device"]],
        )
        deploy_action = job.pipeline.find_action(MassStorage)
        tftp_deploy_action = job.pipeline.find_action(TftpAction)
        self.assertIsNotNone(deploy_action)
        test_dir = deploy_action.get_namespace_data(
            action="test",
            label="results",
            key="lava_test_results_dir",
            parameters=tftp_deploy_action.parameters,
        )
        self.assertIsNotNone(test_dir)
        self.assertIn("/lava-", test_dir)
        self.assertIsInstance(deploy_action, MassStorage)
        img_params = deploy_action.parameters.get("images", deploy_action.parameters)
        self.assertIn("image", img_params)
        dd_action = deploy_action.pipeline.find_action(DDAction)
        self.assertEqual(
            dd_action.boot_params[dd_action.parameters["device"]]["uuid"],
            "usb-SanDisk_Ultra_20060775320F43006019-0:0",
        )
        self.assertIsNotNone(
            dd_action.get_namespace_data(
                action=dd_action.name, label="u-boot", key="boot_part"
            )
        )
        self.assertIsNotNone(
            dd_action.get_namespace_data(
                action="uboot-from-media", label="uuid", key="boot_part"
            )
        )
        self.assertEqual(
            "0",
            "%s"
            % dd_action.get_namespace_data(
                action=dd_action.name, label="u-boot", key="boot_part"
            ),
        )
        self.assertIsInstance(
            dd_action.get_namespace_data(
                action="uboot-from-media", label="uuid", key="boot_part"
            ),
            str,
        )
        self.assertEqual(
            "0:1",
            dd_action.get_namespace_data(
                action="uboot-from-media", label="uuid", key="boot_part"
            ),
        )
        self.assertIsNotNone(
            dd_action.get_namespace_data(
                action="uboot-prepare-kernel", label="bootcommand", key="bootcommand"
            )
        )

    def test_deployment(self):
        self._check_deployment("cubie1", "cubietruck-removable.yaml")

    def test_writer_deployment(self):
        self._check_deployment("cubie1", "cubietruck-removable-with-writer.yaml")

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_juno_deployment(self, which_mock):
        factory = Factory()
        job_filename = "juno-uboot-removable.yaml"
        job = factory.create_job(
            "juno-uboot-01",
            f"sample_jobs/{job_filename}",
        )
        job.validate()
        description_ref = self.pipeline_reference(job_filename, job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        self.assertEqual(job.pipeline.errors, [])
        self.assertIn("usb", job.device["parameters"]["media"].keys())
        deploy_params = [
            methods
            for methods in job.parameters["actions"]
            if "deploy" in methods.keys()
        ][1]["deploy"]
        self.assertIn("device", deploy_params)
        self.assertIn(deploy_params["device"], job.device["parameters"]["media"]["usb"])
        self.assertIn(
            "uuid", job.device["parameters"]["media"]["usb"][deploy_params["device"]]
        )
        self.assertIn(
            "device_id",
            job.device["parameters"]["media"]["usb"][deploy_params["device"]],
        )
        self.assertNotIn(
            "boot_part",
            job.device["parameters"]["media"]["usb"][deploy_params["device"]],
        )
        tftp_deploys = job.pipeline.find_all_actions(TftpAction)
        self.assertEqual(len(tftp_deploys), 2)
        first_deploy = tftp_deploys[0]
        second_deploy = tftp_deploys[1]
        self.assertIsNotNone(first_deploy)
        self.assertIsNotNone(second_deploy)
        self.assertEqual("openembedded", first_deploy.parameters["namespace"])
        self.assertEqual("android", second_deploy.parameters["namespace"])
        self.assertNotIn("deployment_data", first_deploy.parameters)
        self.assertNotIn("deployment_data", second_deploy.parameters)

        storage_deploy_action = job.pipeline.find_action(MassStorage)
        job.pipeline.find_action(DownloaderAction)
        self.assertEqual("android", storage_deploy_action.parameters["namespace"])

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_mustang_deployment(self, which_mock):
        factory = Factory()
        job_filename = "mustang-secondary-media.yaml"
        job = factory.create_job(
            "mustang1",
            f"sample_jobs/{job_filename}",
        )
        job.validate()
        description_ref = self.pipeline_reference(job_filename, job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        description_ref = self.pipeline_reference("mustang-media.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        self.assertIn("sata", job.device["parameters"]["media"].keys())
        deploy_params = [
            methods
            for methods in job.parameters["actions"]
            if "deploy" in methods.keys()
        ][1]["deploy"]
        self.assertIn("device", deploy_params)
        self.assertIn(
            deploy_params["device"], job.device["parameters"]["media"]["sata"]
        )
        self.assertIn(
            "uuid", job.device["parameters"]["media"]["sata"][deploy_params["device"]]
        )
        self.assertIn(
            "device_id",
            job.device["parameters"]["media"]["sata"][deploy_params["device"]],
        )
        self.assertEqual(
            "hd0",
            job.device["parameters"]["media"]["sata"][deploy_params["device"]][
                "grub_interface"
            ],
        )

        grub_deploys = job.pipeline.find_all_actions(GrubMainAction)
        self.assertEqual(len(grub_deploys), 2)
        first_deploy = grub_deploys[0]
        second_deploy = grub_deploys[1]
        self.assertEqual("nfsdeploy", first_deploy.parameters["namespace"])
        self.assertEqual("satadeploy", second_deploy.parameters["namespace"])

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_secondary_media(self, which_mock):
        factory = Factory()
        job_filename = "mustang-secondary-media.yaml"
        job = factory.create_job(
            "mustang1",
            f"sample_jobs/{job_filename}",
        )
        job.validate()
        description_ref = self.pipeline_reference(job_filename, job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        grub_nfs, grub_main = sorted(
            job.pipeline.find_all_actions(GrubMainAction),
            key=lambda x: x.parameters["namespace"],
        )

        grub_nfs_media_action = grub_nfs.pipeline.find_action(BootloaderSecondaryMedia)
        self.assertEqual(
            None,
            grub_nfs_media_action.get_namespace_data(
                action="download-action", label="file", key="kernel"
            ),
        )
        self.assertEqual(
            None,
            grub_nfs_media_action.get_namespace_data(
                action="compress-ramdisk", label="file", key="ramdisk"
            ),
        )
        self.assertEqual(
            None,
            grub_nfs_media_action.get_namespace_data(
                action="download-action", label="file", key="dtb"
            ),
        )
        self.assertEqual(
            None,
            grub_nfs_media_action.get_namespace_data(
                action=grub_nfs_media_action.name, label="file", key="root"
            ),
        )

        grub_main_media_action = grub_main.pipeline.find_action(
            BootloaderSecondaryMedia
        )
        self.assertIsInstance(grub_main_media_action, BootloaderSecondaryMedia)
        self.assertIsNotNone(
            grub_main_media_action.get_namespace_data(
                action="download-action", label="file", key="kernel"
            )
        )
        self.assertIsNotNone(
            grub_main_media_action.get_namespace_data(
                action="compress-ramdisk", label="file", key="ramdisk"
            )
        )
        self.assertIsNotNone(
            grub_main_media_action.get_namespace_data(
                action="download-action", label="file", key="ramdisk"
            )
        )
        self.assertEqual(
            "",
            grub_main_media_action.get_namespace_data(
                action="download-action", label="file", key="dtb"
            ),
        )
        self.assertIsNotNone(
            grub_main_media_action.get_namespace_data(
                action=grub_main_media_action.name, label="uuid", key="root"
            )
        )
        self.assertIsNotNone(
            grub_main_media_action.get_namespace_data(
                action=grub_main_media_action.name, label="uuid", key="boot_part"
            )
        )

    @unittest.skipIf(infrastructure_error("mkimage"), "u-boot-tools not installed")
    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_primary_media(self, which_mock):
        """
        Test that definitions of secondary media do not block submissions
        using primary media
        """
        job_filename = "uboot-ramdisk.yaml"
        job = self.factory.create_job(
            "bbb-01",
            f"sample_jobs/{job_filename}",
        )
        job.validate()
        description_ref = self.pipeline_reference(job_filename, job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        self.assertEqual(job.pipeline.errors, [])
        self.assertIn("usb", job.device["parameters"]["media"].keys())

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_substitutions(self, which_mock):
        """
        Test substitution of secondary media values into u-boot commands

        Unlike most u-boot calls, removable knows in advance all the values it
        needs to substitute into the boot commands for the secondary deployment
        as these are fixed by the device config and the image details from the
        job submission.
        """
        job_filename = "cubietruck-removable.yaml"
        job = self.factory.create_job(
            "cubie1",
            f"sample_jobs/{job_filename}",
        )
        job.validate()
        description_ref = self.pipeline_reference(job_filename, job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        cubie = job.device
        boot_params = [
            methods for methods in job.parameters["actions"] if "boot" in methods.keys()
        ][1]["boot"]
        self.assertIn("ramdisk", boot_params)
        self.assertIn("kernel", boot_params)
        self.assertIn("dtb", boot_params)
        self.assertIn("root_uuid", boot_params)
        self.assertIn("boot_part", boot_params)
        self.assertNotIn("type", boot_params)
        self.assertGreater(len(job.pipeline.actions), 1)
        self.assertIsNotNone(job.pipeline.actions[1].pipeline)

        _, u_boot_action = job.pipeline.find_all_actions(UBootAction)
        overlay = u_boot_action.pipeline.find_action(BootloaderCommandOverlay)

        self.assertIsNotNone(
            overlay.get_namespace_data(
                action="storage-deploy", label="u-boot", key="device"
            )
        )

        methods = cubie["actions"]["boot"]["methods"]
        self.assertIn("u-boot", methods)
        self.assertIn("usb", methods["u-boot"])
        self.assertIn("commands", methods["u-boot"]["usb"])
        commands_list = methods["u-boot"]["usb"]["commands"]
        device_id = u_boot_action.get_namespace_data(
            action="storage-deploy", label="u-boot", key="device"
        )
        self.assertIsNotNone(device_id)
        kernel_type = u_boot_action.parameters["kernel_type"]
        bootcommand = map_kernel_uboot(
            kernel_type, device_params=cubie.get("parameters")
        )
        substitutions = {
            "{BOOTX}": "%s %s %s %s"
            % (
                bootcommand,
                cubie["parameters"][bootcommand]["kernel"],
                cubie["parameters"][bootcommand]["ramdisk"],
                cubie["parameters"][bootcommand]["dtb"],
            ),
            "{RAMDISK}": boot_params["ramdisk"],
            "{KERNEL}": boot_params["kernel"],
            "{DTB}": boot_params["dtb"],
            "{ROOT}": boot_params["root_uuid"],
            "{ROOT_PART}": "%s:%s"
            % (
                cubie["parameters"]["media"]["usb"][device_id]["device_id"],
                u_boot_action.parameters["boot_part"],
            ),
        }
        self.assertEqual(
            "bootz 0x42000000 0x43300000 0x43000000", substitutions["{BOOTX}"]
        )
        self.assertEqual(
            "/boot/initrd.img-3.16.0-4-armmp-lpae.u-boot", substitutions["{RAMDISK}"]
        )
        commands = substitute(commands_list, substitutions)
        print(commands)
        self.assertEqual(
            commands,
            [
                "usb start",
                "setenv autoload no",
                "load usb 0:0:1 {KERNEL_ADDR} /boot/vmlinuz-3.16.0-4-armmp-lpae",
                "load usb 0:0:1 {RAMDISK_ADDR} /boot/initrd.img-3.16.0-4-armmp-lpae.u-boot",
                "setenv initrd_size ${filesize}",
                "load usb 0:0:1 {DTB_ADDR} /boot/dtb-3.16.0-4-armmp-lpae",
                "console=ttyS0,115200n8 root=UUID=159d17cc-697c-4125-95a0-a3775e1deabe  ip=dhcp",
                "bootz 0x42000000 0x43300000 0x43000000",
            ],
        )
