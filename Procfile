web: python3 ./manage.py runserver 0.0.0.0:8000 $LAVA_WEB_OPTS
master: mkdir -p tmp/media && python3 ./manage.py lava-master --level DEBUG --log-file - --user $(id --user --name) --group $(id --group --name) $LAVA_MASTER_OPTS
logs: mkdir -p tmp/media && python3 ./manage.py lava-logs --level DEBUG --log-file - --user $(id --user --name) --group $(id --group --name) $LAVA_LOGS_OPTS
slave: sudo PYTHONPATH=. python3 lava/dispatcher/lava-slave --level DEBUG --log-file - --master tcp://localhost:5556 --socket-addr tcp://localhost:5555 --slave-dir $(pwd)/tmp/slave $LAVA_SLAVE_OPTS
