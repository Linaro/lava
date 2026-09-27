# Development helpers for LAVA. Every recipe runs through "uv run", so no
# virtualenv needs to be activated.  "just --list" lists the recipes.
#
# Useful overrides:
#   just test-scheduler ARGS="-k ldap -x"   # extra pytest arguments
#   just DATABASE_URL=postgres://... server # use another database

database_url := env_var_or_default('DATABASE_URL', 'sqlite:///db.sqlite')
database_test_url := env_var_or_default('DATABASE_TEST_URL', 'sqlite:///:memory:')
user := `id --user --name`
args := env_var_or_default('ARGS', '')

# sudo resets PATH (secure_path), so `sudo uv` breaks unless uv_bin is absolute.
uv_bin := env_var_or_default('UV_BIN', `command -v uv || { echo "uv not found in PATH, see https://docs.astral.sh/uv/getting-started/installation/" >&2; exit 1; }`)
uv := uv_bin + ' run --frozen'
uv_server := 'DATABASE_URL=' + database_url + ' ' + uv + ' --extra server -- manage.py'
uv_dev := uv + ' --all-extras --'
pytest_server := 'DATABASE_URL=' + database_test_url + ' ' + uv + ' --extra dev --extra server -- pytest -v'

# Show this help
[default]
help:
  just --list

# Services

# Run lava-coordinator
coordinator:
  {{ uv }} --extra coordinator -- python3 lava/coordinator/lava-coordinator --log-file - --level DEBUG --config etc/lava-coordinator.conf

# Run lava-publisher
publisher:
  {{ uv_server }} lava-publisher --log-file - -u {{ user }} -g {{ user }}

# Run lava-scheduler
scheduler:
  {{ uv_server }} lava-scheduler --log-file - -u {{ user }} -g {{ user }}

# Run the django development server on http://localhost:8000
server:
  {{ uv_server }} runserver

# Run lava-worker (needs sudo)
worker:
  sudo {{ uv }} --extra dispatcher -- lava_dispatcher/worker.py --url http://localhost:8000 --log-file - --ws-url http://localhost:8001/ws/

# Run every service at once (Ctrl-C stops them all)
run:
  just --parallel coordinator publisher scheduler server worker

# Database and shell

# Apply the database migrations
init:
  {{ uv_server }} migrate

# Generate the missing database migrations
makemigrations:
  {{ uv_server }} makemigrations

# Create an admin account
superuser:
  {{ uv_server }} createsuperuser

# Open a django shell
shell:
  {{ uv_server }} shell

# Tests

# Run the lava_common tests
test-common:
  {{ uv }} --extra dev -- pytest -v {{ args }} tests/lava_common

# Run the lava-coordinator tests
test-coordinator:
  {{ uv }} --extra dev --extra coordinator -- pytest -v {{ args }} tests/lava_coordinator

# Run the lava-dispatcher tests
test-dispatcher:
  {{ uv }} --extra dev --extra dispatcher -- pytest -v {{ args }} tests/lava_dispatcher

# Run the lava-dispatcher-host tests
test-dispatcher-host:
  {{ uv }} --extra dev --extra dispatcher-host -- pytest -v {{ args }} tests/lava_dispatcher_host

# Run the REST API tests
test-rest:
  {{ pytest_server }} {{ args }} tests/lava_rest_app

# Run the lava_results_app tests
test-results:
  {{ pytest_server }} {{ args }} tests/lava_results_app

# Run the lava_scheduler_app tests
test-scheduler:
  {{ pytest_server }} {{ args }} tests/lava_scheduler_app

# Run the lava_server tests
test-server:
  {{ pytest_server }} {{ args }} tests/lava_server

# Run the XML-RPC tests
test-xmlrpc:
  {{ pytest_server }} {{ args }} tests/linaro_django_xmlrpc

# Run every lava-server test
test-lava-server: test-rest test-results test-scheduler test-server test-xmlrpc

# Run every lava-dispatcher test
test-lava-dispatcher: test-common test-coordinator test-dispatcher test-dispatcher-host

# Run the full test suite
tests: test-lava-server test-lava-dispatcher

# Run the full test suite and write htmlcov/ and coverage.xml
coverage:
  DATABASE_URL={{ database_test_url }} {{ uv_dev }} pytest --cache-clear -v --cov --cov-report=term --cov-report=xml:coverage.xml --cov-report=html:htmlcov {{ args }} tests/

# Static analysis

# Run ruff (check and format) over the whole tree
lint:
  {{ uv_dev }} pre-commit run ruff-check --show-diff-on-failure --all-files
  {{ uv_dev }} pre-commit run ruff-format --show-diff-on-failure --all-files

# Run pylint over the whole tree
pylint:
  {{ uv_dev }} pre-commit run pylint --show-diff-on-failure --all-files

# Type check the modules covered by the CI
mypy:
  {{ uv_dev }} pre-commit run mypy --show-diff-on-failure --all-files
  {{ uv_dev }} pre-commit run pyrefly-check --show-diff-on-failure --all-files

# Run every pre-commit hook over the whole tree
pre-commit:
  {{ uv_dev }} pre-commit run --show-diff-on-failure --all-files

# Fail if a model change is missing its migration
check-migrations:
  {{ uv_server }} makemigrations --check --dry-run

# Run every checks
check: pre-commit check-migrations

# Documentation

# Build the documentation into doc/site
doc:
  {{ uv }} --extra docs -- mkdocs build -f doc/mkdocs.yml

# Serve the documentation on http://localhost:8080
doc-serve:
  {{ uv }} --extra docs -- mkdocs serve -f doc/mkdocs.yml -a localhost:8080

# Misc

# Remove the test, coverage and lint artifacts
clean:
  rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov coverage.xml doc/site dispatcher.xml server.xml
