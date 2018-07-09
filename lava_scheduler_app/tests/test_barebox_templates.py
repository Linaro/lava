# pylint: disable=superfluous-parens,ungrouped-imports
from lava_scheduler_app.tests.test_base_templates import (
    BaseTemplate,
    prepare_jinja_template,
)

# pylint: disable=too-many-branches,too-many-public-methods
# pylint: disable=too-many-nested-blocks


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
