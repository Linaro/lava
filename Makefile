PIP_INSTALL = ./.virtualenv/bin/pip install

default: build

.virtualenv:
	virtualenv --setuptools .virtualenv

install-virtualenv: .virtualenv

develop: install-virtualenv setup.py
	./.virtualenv/bin/python setup.py develop --script-dir=./bin/
	$(PIP_INSTALL) -r requirements.txt

build: develop
	[ -f database.db ] || ./bin/manage syncdb --noinput