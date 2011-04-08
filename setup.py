
from setuptools import setup, find_packages

setup(
    name="lava",
    version="0.0.1",
    url='XXX',
    license='XXX',
    description="XXX",
    author='XXX',
    packages=find_packages(),
    scripts = [
    ],
    entry_points = {
        'console_scripts': [
            'manage = lava.scheduler.interface.manage:run',
        ],
    },
)
