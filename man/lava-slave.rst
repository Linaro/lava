Description
###########

Summary
*******

``lava-slave`` runs the connection to the lava master over ZMQ to
manage LAVA test jobs running on the reserved device, sending log
messages back to the master. ``lava-slave`` runs as a daemon.

Usage
*****

lava-slave [-h] [--hostname HOSTNAME] --master MASTER --socket-addr
           SOCKET_ADDR [--socks-proxy SOCKS_PROXY] [--ipv6] [--encrypt]
           [--master-cert MASTER_CERT] [--slave-cert SLAVE_CERT]
           [--log-file LOG_FILE] [--level {DEBUG,ERROR,INFO,WARN}]

Options
*******

Options can be passed by editing /etc/default/lava-slave or
/etc/lava-dispatcher/lava-slave

optional arguments:
  -h, --help            show this help message and exit
  --hostname HOSTNAME   Name of the slave

network:
  --master MASTER       Main master socket
  --socket-addr SOCKET_ADDR
                        Log socket
  --socks-proxy SOCKS_PROXY
                        Connect using a socks proxy
  --ipv6                Enable IPv6

encryption:
  --encrypt             Encrypt messages
  --master-cert MASTER_CERT
                        Master certificate file
  --slave-cert SLAVE_CERT
                        Slave certificate file

logging:
  --log-file LOG_FILE   Log file for the slave logs
  --level {DEBUG,ERROR,INFO,WARN}, -l {DEBUG,ERROR,INFO,WARN}
                        Log level, default to INFO

Encryption
**********

Some LAVA instances require the ZMQ connection to the master to be
encrypted. For more information on configuring lava-slave to use
encryption support, see the lava-server documentation on your
local instance or at:
https://validation.linaro.org/static/docs/v2/pipeline-server.html#zmq-curve

You will need to contact the admin of the instance to obtain the
certificate of the master to which this slave should connect.
