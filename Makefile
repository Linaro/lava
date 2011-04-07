PIP_INSTALL = ./.virtualenv/bin/pip install

default: develop

.virtualenv:
	virtualenv --setuptools .virtualenv

install-virtualenv: .virtualenv

develop: install-virtualenv setup.py
	./.virtualenv/bin/python setup.py develop --script-dir=./bin/
	$(PIP_INSTALL) -r requirements.txt
