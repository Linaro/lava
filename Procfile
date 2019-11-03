web: python3 ./manage.py runserver 0.0.0.0:8000
master: mkdir -p tmp/media && python3 ./manage.py lava-master --level DEBUG --log-file - --user $(id --user --name) --group $(id --group --name)
logs: mkdir -p tmp/media && python3 ./manage.py lava-logs --level DEBUG --log-file - --user $(id --user --name) --group $(id --group --name)
slave: sudo PYTHONPATH=. python3 lava/dispatcher/lava-slave --level DEBUG --log-file - --master tcp://localhost:5556 --socket-addr tcp://localhost:5555 --slave-dir $(pwd)/tmp/slave
