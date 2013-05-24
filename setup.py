from setuptools import setup, find_packages

setup(
    name='lava-server',
    version="0.0.0",
    packages=find_packages(),
    license="AGPL",
    description="LAVA Server",
    author='Linaro Validation Team',
    author_email='linaro-dev@lists.linaro.org',
    install_requires=[
        "json-schema-validator >= 2.3",
        "linaro-dashboard-bundle",
        'versiontools >= 1.8',
    ],
    setup_requires=[
        'versiontools >= 1.8',
    ],
    scripts = [
    ],
    zip_safe=False,
    include_package_data=True)
