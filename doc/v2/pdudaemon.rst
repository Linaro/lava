.. _pdudaemon:

PDU Daemon
**********

APC PDUs (Power Distribution Unit) only support one control session at a time. 
In a :term:`distributed deployment` LAVA installation with multiple
:term:`remote worker` machines there is a possibility that more than one
dispatcher may attempt to access a PDU simultaneously. In this case the
power control request will only succeed from the dispatcher which was
first.

Multinode jobs are more likely to trigger this issue as they cause many jobs
to be started at the same time.

To solve this problem we use a project called 
`lavapdu <https://git.linaro.org/lava/lavapdu.git>`_.
Instead of each dispatcher accessing the PDUs directly, dispatchers make
requests to a queueing daemon which executes them sequentially.

The project source is available here: https://git.linaro.org/lava/lavapdu.git
Packages for Debian and Ubuntu will be available shortly.

A Postgres server is required with a database created, and postgres
credentials to read/write to the database.

Example config file for lavapdu server::

 {
   "hostname": "0.0.0.0",
   "port": 16421,
   "dbhost": "127.0.0.1",
   "dbuser": "pdudaemon",
   "dbpass": "pdudaemon",
   "dbname": "lavapdu"
 }
 
Hostname is the interface IP address that PDU Daemon will attempt to bind to.

Example invocation of pduclient::

 # ./pduclient --daemon pdu_daemon_hostname --hostname pdu_hostname --command pdu_command --port pdu_port_number
 $ ./pduclient --daemon services --hostname pdu12 --command reboot --port 01

this will ask the PDU Daemon running on "services" to reboot port 1 on the pdu with hostname pdu12.
