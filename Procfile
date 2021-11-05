web: python3 ./manage.py runserver 0.0.0.0:8000 $LAVA_WEB_OPTS
publisher: python3 ./manage.py lava-publisher --level DEBUG --log-file - --user $(id --user --name) --group $(id --group --name) $LAVA_PUBLISHER_OPTS
scheduler: mkdir -p tmp/media && python3 ./manage.py lava-scheduler --level DEBUG --log-file - --user $(id --user --name) --group $(id --group --name) $LAVA_SCHEDULER_OPTS
worker: sudo PYTHONPATH=. python3 lava/dispatcher/lava-worker --level DEBUG --log-file - --url http://localhost:8000/ --ws-url http://localhost:8001/ --worker-dir $(pwd)/tmp/worker $LAVA_WORKER_OPTS
lava-dispatcher-host: sudo PYTHONPATH=. python3 -m lava_dispatcher_host.server --log-level=DEBUG
