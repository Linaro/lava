from setuptools import setup, find_packages

setup(
    name='lava-server',
    version="0.0",
    author="Michael Hudson-Doyle",
    author_email="michael.hudson@linaro.org",
    packages=find_packages(),
    license="AGPL",
    description="LAVA Server",
    install_requires=[
    ],
    setup_requires=[
    ],
    tests_require=[
    ],
    zip_safe=False,
    include_package_data=True)
