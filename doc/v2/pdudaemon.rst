.. _pdudaemon:

PDUDaemon
**********

The `PDUDaemon project <https://github.com/pdudaemon/pdudaemon>` presents a
simple interface to control most popular PDU (Power Distribution Unit) models.
LAVA can be configured to use PDUDaemon requests to control power on devices in
your lab.

Some PDUs only support one control session at a time.
In a :term:`distributed deployment` LAVA installation with multiple
:term:`remote worker` machines there is a possibility that more than one
dispatcher may attempt to access a PDU simultaneously. In this case the power
control request will only succeed from the dispatcher which was first.

Multinode jobs are more likely to trigger this issue as they cause many jobs to
be started at the same time.

To avoid this problem, instead of each dispatcher accessing the PDUs directly,
dispatchers can make requests to PDUDaemon which executes them sequentially.

The project source is available here: https://github.com/pdudaemon/pdudaemon
Packages for Debian and Ubuntu will be available shortly.
An earlier version of PDUDaemon was called lavapdu, but the packages in
Debian are out of date and should not be used.

Example config file for PDUDaemon
`here <https://github.com/pdudaemon/pdudaemon/blob/master/share/pdudaemon.conf>``

For more information see the `PDUDeamon README
<https://github.com/pdudaemon/pdudaemon/blob/master/README.md>`
