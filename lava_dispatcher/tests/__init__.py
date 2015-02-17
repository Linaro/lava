import unittest


def test_suite():
    module_names = [
        'lava_dispatcher.tests.test_config',
        'lava_dispatcher.tests.test_device_version',
        'linaro_dashboard_bundle.tests',
        'lava_dispatcher.tests.test_job',
        'lava_dispatcher.pipeline.test.test_basic',
        'lava_dispatcher.pipeline.test.test_defs',
        'lava_dispatcher.pipeline.test.test_devices',
        'lava_dispatcher.pipeline.test.test_lavashell',
        'lava_dispatcher.pipeline.test.test_retries',
        'lava_dispatcher.pipeline.test.test_removable',
        'lava_dispatcher.pipeline.test.test_uboot',
        'lava_dispatcher.pipeline.test.test_multi',
        'lava_dispatcher.pipeline.test.test_kexec',
        'lava_dispatcher.pipeline.test.test_kvm',
        'lava_dispatcher.pipeline.test.test_multinode',
        'lava_dispatcher.pipeline.test.test_connections',
        #  'lava_dispatcher.pipeline.test.test_utils',
        'lava_dispatcher.pipeline.test.test_repeat',
    ]
    loader = unittest.TestLoader()
    return loader.loadTestsFromNames(module_names)
