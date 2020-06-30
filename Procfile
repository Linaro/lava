web: python3 ./manage.py runserver 0.0.0.0:8000 $LAVA_WEB_OPTS
master: mkdir -p tmp/media && python3 ./manage.py lava-master --level DEBUG --log-file - --user $(id --user --name) --group $(id --group --name) $LAVA_MASTER_OPTS
logs: mkdir -p tmp/media && python3 ./manage.py lava-logs --level DEBUG --log-file - --user $(id --user --name) --group $(id --group --name) $LAVA_LOGS_OPTS
worker: sudo PYTHONPATH=. python3 lava/dispatcher/lava-worker --level DEBUG --log-file - --url http://localhost:8000/ --ws-url http://localhost:8001/ --worker-dir $(pwd)/tmp/worker $LAVA_WORKER_OPTS
