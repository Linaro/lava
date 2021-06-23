from tests.lava_scheduler_app.test_base_templates import (
    BaseTemplate,
    prepare_jinja_template,
)


def barebox_helper(self, board):
    data = """{% extends '""" + board + """.jinja2' %}"""
    self.assertTrue(self.validate_data(board + "-0", data))
    template_dict = prepare_jinja_template(board + "-0", data, raw=False)
    self.assertIn("barebox", template_dict["actions"]["boot"]["methods"])
    self.assertIn("ramdisk", template_dict["actions"]["boot"]["methods"]["barebox"])
    commands = template_dict["actions"]["boot"]["methods"]["barebox"]["ramdisk"][
        "commands"
    ]
    for command in commands:
        self.assertNotIn("boot ", command)
        self.assertIn("bootm", command)


class TestBareboxTemplates(BaseTemplate.BaseTemplateCases):
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

    def test_imx6ul_pico_hobbit_template(self):
        barebox_helper(self, "imx6ul-pico-hobbit")

    def test_imx23_olinuxino_template(self):
        barebox_helper(self, "imx23-olinuxino")

    def test_imx28_duckbill_template(self):
        barebox_helper(self, "imx28-duckbill")

    def test_imx27_phytec_phycard_s_rdk_template(self):
        barebox_helper(self, "imx27-phytec-phycard-s-rdk")

    def test_imx53_qsrb_template(self):
        barebox_helper(self, "imx53-qsrb")

    def test_imx6l_riotboard_template(self):
        barebox_helper(self, "imx6dl-riotboard")

    def test_imx6qp_wandboard_revd1_template(self):
        barebox_helper(self, "imx6qp-wandboard-revd1")

    def test_imx8mq_zii_ultra_zest_template(self):
        barebox_helper(self, "imx8mq-zii-ultra-zest")

    def test_dove_cubox_template(self):
        barebox_helper(self, "dove-cubox")

    def test_ar9331_dpt_module_template(self):
        barebox_helper(self, "ar9331-dpt-module")

    def test_socfpga_cyclone5_socrates_template(self):
        barebox_helper(self, "socfpga-cyclone5-socrates")

    def test_stm32mp157c_lxa_mc1_template(self):
        barebox_helper(self, "stm32mp157c-lxa-mc1")

    def test_jh7100_beaglev_starlight_template(self):
        barebox_helper(self, "jh7100-beaglev-starlight")
