import os
import yaml
from lava_scheduler_app.models import DeviceDictionary
from lava_scheduler_app.utils import (
    jinja_template_path,
    devicedictionary_to_jinja2,
    prepare_jinja_template,
)
from lava_scheduler_app.tests.test_pipeline import YamlFactory
from lava_scheduler_app.tests.test_submission import TestCaseWithFactory


class YamlMenuFactory(YamlFactory):

    def make_fake_mustang_device(self, hostname='fakemustang1'):  # pylint: disable=no-self-use
        mustang = DeviceDictionary(hostname=hostname)
        mustang.parameters = {'extends': 'mustang-uefi.jinja2'}
        mustang.save()
        return hostname

    def make_job_data(self, actions=None, **kw):
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs', 'mustang-menu-ramdisk.yaml')
        with open(sample_job_file, 'r') as test_support:
            data = yaml.load(test_support)
        data.update(kw)
        return data


class TestPipelineMenu(TestCaseWithFactory):  # pylint: disable=too-many-ancestors
    """
    Test the building and override support of pipeline menus from submission YAML
    """
    def setUp(self):
        super(TestPipelineMenu, self).setUp()
        self.factory = YamlMenuFactory()
        self.jinja_path = jinja_template_path(system=False)
        self.device_type = self.factory.make_device_type(name='mustang-uefi')
        self.conf = {
            'extends': 'mustang-uefi.jinja2',
            'tftp_mac': '52:54:00:12:34:59',
        }

    def test_make_job_yaml(self):
        data = yaml.load(self.factory.make_job_yaml())
        self.assertIn('device_type', data)
        self.assertNotIn('timeout', data)
        self.assertIn('timeouts', data)
        self.assertIn('job', data['timeouts'])
        self.assertIn('priority', data)

    def test_menu_device(self):
        job_ctx = {}
        hostname = 'mustang01'
        device_dict = DeviceDictionary(hostname=hostname)
        device_dict.parameters = self.conf
        device_dict.save()
        device = self.factory.make_device(self.device_type, hostname)
        self.assertEqual(device.device_type.name, 'mustang-uefi')

        device_data = devicedictionary_to_jinja2(
            device_dict.parameters,
            device_dict.parameters['extends']
        )
        template = prepare_jinja_template(hostname, device_data, system_path=False, path=self.jinja_path)
        config_str = template.render(**job_ctx)
        self.assertIsNotNone(config_str)
        config = yaml.load(config_str)
        self.assertIsNotNone(config)
        self.assertEqual(config['device_type'], self.device_type.name)
        self.assertNotIn('parameters', config)
        self.assertIsNotNone(config['actions']['boot']['methods']['uefi-menu']['nfs'])
        menu_data = config['actions']['boot']['methods']['uefi-menu']['nfs']
        tftp_menu = [item for item in menu_data if 'items' in item['select'] and 'TFTP' in item['select']['items'][0]][0]
        tftp_mac = self.conf['tftp_mac']
        # value from device dictionary correctly replaces device type default
        self.assertIn(tftp_mac, tftp_menu['select']['items'][0])

    def test_menu_context(self):
        job_ctx = {
            'menu_early_printk': '',
            'menu_interrupt_prompt': 'Default boot will start in',
            'base_ip_args': 'ip=dhcp'
        }
        hostname = self.factory.make_fake_mustang_device()
        device_dict = DeviceDictionary.get(hostname)
        device_data = devicedictionary_to_jinja2(
            device_dict.parameters,
            device_dict.parameters['extends']
        )
        template = prepare_jinja_template(hostname, device_data, system_path=False, path=self.jinja_path)
        config_str = template.render(**job_ctx)
        self.assertIsNotNone(config_str)
        config = yaml.load(config_str)
        self.assertIsNotNone(config['actions']['boot']['methods']['uefi-menu']['nfs'])
        menu_data = config['actions']['boot']['methods']['uefi-menu']
        # assert that menu_interrupt_prompt replaces the default 'The default boot selection will start in'
        self.assertEqual(
            menu_data['parameters']['interrupt_prompt'],
            job_ctx['menu_interrupt_prompt']
        )
        # assert that menu_early_printk replaces the default earlyprintk default
        self.assertEqual(
            [e for e in menu_data['nfs'] if 'enter' in e['select'] and 'new Entry' in e['select']['wait']][0]['select']['enter'],
            'console=ttyS0,115200  debug root=/dev/nfs rw nfsroot={NFS_SERVER_IP}:{NFSROOTFS},tcp,hard,intr ip=dhcp'
        )
