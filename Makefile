# Development helpers for LAVA.
#
# Every recipe runs through "uv run", so no virtualenv needs to be activated.
# Run "make" or "make help" to list the available targets.
#
# Useful overrides:
#   make test-scheduler ARGS="-k ldap -x"   # extra pytest arguments
#   make server DATABASE_URL=postgres://... # use another database

DATABASE_URL ?= sqlite:///db.sqlite
DATABASE_TEST_URL ?= sqlite:///:memory:
USER ?= $(shell id --user --name)
ARGS ?=

# Absolute path to uv: sudo resets PATH to its own secure_path, which usually
# does not contain ~/.local/bin, so "sudo uv" would not be found.  Override
# with "make worker UV_BIN=/path/to/uv" when uv lives somewhere unusual.
UV_BIN := $(shell command -v uv 2>/dev/null)

# Command prefixes: each one pulls in the extras that the code under it needs.
# They are recursively expanded so that the missing-uv error below is only
# reported by the targets that actually need uv.
UV = $(if $(UV_BIN),$(UV_BIN),$(error uv not found in PATH, see https://docs.astral.sh/uv/getting-started/installation/)) run --frozen
COORDINATOR = $(UV) --extra coordinator --
DISPATCHER = sudo $(UV) --extra dispatcher --
SERVER = DATABASE_URL=$(DATABASE_URL) $(UV) --extra server -- manage.py
DEV = $(UV) --all-extras --

PYTEST = $(UV) --extra dev -- pytest -v $(ARGS)
PYTEST_DISPATCHER = $(UV) --extra dev --extra dispatcher -- pytest -v $(ARGS)
PYTEST_SERVER = DATABASE_URL=$(DATABASE_TEST_URL) $(UV) --extra dev --extra server -- pytest -v $(ARGS)

.DEFAULT_GOAL := help

##@ Services

.PHONY: coordinator
coordinator: ## Run lava-coordinator
	$(COORDINATOR) python3 lava/coordinator/lava-coordinator --log-file - --level DEBUG --config etc/lava-coordinator.conf

.PHONY: publisher
publisher: ## Run lava-publisher
	$(SERVER) lava-publisher --log-file - -u $(USER) -g $(USER)

.PHONY: scheduler
scheduler: ## Run lava-scheduler
	$(SERVER) lava-scheduler --log-file - -u $(USER) -g $(USER)

.PHONY: server
server: ## Run the django development server on http://localhost:8000
	$(SERVER) runserver

.PHONY: worker
worker: ## Run lava-worker (needs sudo)
	$(DISPATCHER) lava_dispatcher/worker.py --url http://localhost:8000 --log-file - --ws-url http://localhost:8001/ws/

.PHONY: run
run: ## Run every service at once (Ctrl-C stops them all)
	$(MAKE) -j5 coordinator publisher scheduler server worker

##@ Database and shell

.PHONY: init
init: ## Apply the database migrations
	$(SERVER) migrate

.PHONY: makemigrations
makemigrations: ## Generate the missing database migrations
	$(SERVER) makemigrations

.PHONY: superuser
superuser: ## Create an admin account
	$(SERVER) createsuperuser

.PHONY: shell
shell: ## Open a django shell
	$(SERVER) shell

##@ Tests

.PHONY: test-common
test-common: ## Run the lava_common tests
	$(PYTEST) tests/lava_common

.PHONY: test-coordinator
test-coordinator: ## Run the lava-coordinator tests
	$(UV) --extra dev --extra coordinator -- pytest -v $(ARGS) tests/lava_coordinator

.PHONY: test-dispatcher
test-dispatcher: ## Run the lava-dispatcher tests
	$(PYTEST_DISPATCHER) tests/lava_dispatcher

.PHONY: test-dispatcher-host
test-dispatcher-host: ## Run the lava-dispatcher-host tests
	$(UV) --extra dev --extra dispatcher-host -- pytest -v $(ARGS) tests/lava_dispatcher_host

.PHONY: test-rest
test-rest: ## Run the REST API tests
	$(PYTEST_SERVER) tests/lava_rest_app

.PHONY: test-results
test-results: ## Run the lava_results_app tests
	$(PYTEST_SERVER) tests/lava_results_app

.PHONY: test-scheduler
test-scheduler: ## Run the lava_scheduler_app tests
	$(PYTEST_SERVER) tests/lava_scheduler_app

.PHONY: test-server
test-server: ## Run the lava_server tests
	$(PYTEST_SERVER) tests/lava_server

.PHONY: test-xmlrpc
test-xmlrpc: ## Run the XML-RPC tests
	$(PYTEST_SERVER) tests/linaro_django_xmlrpc

.PHONY: test-lava-server
test-lava-server: test-rest test-results test-scheduler test-server test-xmlrpc ## Run every lava-server test

.PHONY: test-lava-dispatcher
test-lava-dispatcher: test-common test-coordinator test-dispatcher test-dispatcher-host ## Run every lava-dispatcher test

.PHONY: tests
tests: test-lava-server test-lava-dispatcher ## Run the full test suite

.PHONY: coverage
coverage: ## Run the full test suite and write htmlcov/ and coverage.xml
	DATABASE_URL=$(DATABASE_TEST_URL) $(DEV) pytest --cache-clear -v \
	  --cov --cov-report=term --cov-report=xml:coverage.xml --cov-report=html:htmlcov \
	  $(ARGS) tests/

##@ Static analysis

.PHONY: lint
lint: ## Run ruff (check and format) over the whole tree
	$(DEV) pre-commit run ruff-check --show-diff-on-failure --all-files
	$(DEV) pre-commit run ruff-format --show-diff-on-failure --all-files

.PHONY: pylint
pylint: ## Run pylint over the whole tree
	$(DEV) pre-commit run pylint --show-diff-on-failure --all-files

.PHONY: mypy
mypy: ## Type check the modules covered by the CI
	$(DEV) ./.gitlab-ci/analyze/mypy.sh

.PHONY: pre-commit
pre-commit: ## Run every pre-commit hook over the whole tree
	$(DEV) pre-commit run --show-diff-on-failure --all-files

.PHONY: check-migrations
check-migrations: ## Fail if a model change is missing its migration
	$(SERVER) makemigrations --check --dry-run

.PHONY: check
check: lint pylint mypy pre-commit check-migations ## Run every checks

##@ Documentation

.PHONY: doc
doc: ## Build the documentation into doc/site
	$(UV) --extra docs -- mkdocs build -f doc/mkdocs.yml

.PHONY: doc-serve
doc-serve: ## Serve the documentation on http://localhost:8080
	$(UV) --extra docs -- mkdocs serve -f doc/mkdocs.yml -a localhost:8080

##@ Misc

.PHONY: clean
clean: ## Remove the test, coverage and lint artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov coverage.xml doc/site
	rm -rf dispatcher.xml server.xml

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make <target>\n"} \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5); next } \
	  /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
