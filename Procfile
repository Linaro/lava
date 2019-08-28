web: python3 lava_server/manage.py runserver_plus --print-sql --verbosity 1 0.0.0.0:8000
master: mkdir -p lava_server/precious/var/lib/lava-server/media && python3 lava_server/manage.py lava-master --level DEBUG --log-file - --user $(id --user --name) --group $(id --group --name)
logs: mkdir -p lava_server/precious/var/lib/lava-server/media && python3 lava_server/manage.py lava-logs --level DEBUG --log-file - --user $(id --user --name) --group $(id --group --name)
slave: sudo PYTHONPATH=. python3 lava/dispatcher/lava-slave --level DEBUG --log-file - --master tcp://localhost:5556 --socket-addr tcp://localhost:5555 --slave-dir $(pwd)/tmp/slave
