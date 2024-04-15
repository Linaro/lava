# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from .test_templates import BaseTemplateTest


class TestBareboxTemplates(BaseTemplateTest):
    """
    Test rendering of jinja2 templates

    When adding or modifying a jinja2 template, add or update the test here.
    Use realistic data - complete exports of the device dictionary preferably.
    Set debug to True to see the content of the rendered templates
    Set system to True to use the system templates - note that this requires
    that the templates in question are in sync with the branch upon which the
    test is run. Therefore, if the templates should be the same, this can be
    used to check that the templates are correct. If there are problems, check
    for a template with a .dpkg-dist extension. Check the diff between the
    checkout and the system file matches the difference between the system file
    and the dpkg-dist version. If the diffs match, copy the dpkg-dist onto the
    system file.
    """

    def barebox_templater(self, board) -> None:
        data = f"{{% extends '{board}.jinja2' %}}"
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertIn("barebox", template_dict["actions"]["boot"]["methods"])
        self.assertIn("ramdisk", template_dict["actions"]["boot"]["methods"]["barebox"])
        commands = template_dict["actions"]["boot"]["methods"]["barebox"]["ramdisk"][
            "commands"
        ]
        for command in commands:
            self.assertNotIn("boot ", command)
            self.assertIn("bootm", command)

    def test_imx6ul_pico_hobbit_template(self):
        self.barebox_templater("imx6ul-pico-hobbit")

    def test_imx23_olinuxino_template(self):
        self.barebox_templater("imx23-olinuxino")

    def test_imx28_duckbill_template(self):
        self.barebox_templater("imx28-duckbill")

    def test_imx27_phytec_phycard_s_rdk_template(self):
        self.barebox_templater("imx27-phytec-phycard-s-rdk")

    def test_imx53_qsrb_template(self):
        self.barebox_templater("imx53-qsrb")

    def test_imx6l_riotboard_template(self):
        self.barebox_templater("imx6dl-riotboard")

    def test_imx6qp_wandboard_revd1_template(self):
        self.barebox_templater("imx6qp-wandboard-revd1")

    def test_imx8mq_zii_ultra_zest_template(self):
        self.barebox_templater("imx8mq-zii-ultra-zest")

    def test_dove_cubox_template(self):
        self.barebox_templater("dove-cubox")

    def test_ar9331_dpt_module_template(self):
        self.barebox_templater("ar9331-dpt-module")

    def test_socfpga_cyclone5_socrates_template(self):
        self.barebox_templater("socfpga-cyclone5-socrates")

    def test_stm32mp157c_lxa_mc1_template(self):
        self.barebox_templater("stm32mp157c-lxa-mc1")

    def test_jh7100_beaglev_starlight_template(self):
        self.barebox_templater("jh7100-beaglev-starlight")
