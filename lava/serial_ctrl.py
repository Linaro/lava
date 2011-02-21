#!/usr/bin/env python

import socket
import select
import Queue


class NetworkSerialController(object):
    """
    Controller for network-over-serial connection to a device
    """

    def __init__(self, addr):
        """
        Connect to a remote serial port using TCP socket to addr.
        The address is a (host, port) tuple
        """
        self.addr = addr
        self.sock = None
        self.cmds = Queue.Queue() # command queue
        self.outgoing = None # for sending the current command (it may not go in one packet)

    def _run_onetime(self):
        if self.outgoing is None:
            try:
                self.outgoing = self.cmds.get_nowait()
                print "Selected next command to send: %r" % self.outgoing
            except Queue.Empty:
                self.outgoing = None
                print "No more commands to process at this time"
        rlist = [self.sock] # always wake for reading
        wlist = [self.sock] if self.outgoing else [] # wake for writing only when we have something to say
        xlist = []
        rlist, wlist, xlist = select.select(rlist, wlist, xlist)
        if rlist:
            print "Reading is possible"
            data = self.sock.recv(76)
            print "Got: %r" % data
        if wlist:
            print "Writing is possible"
            print "Writing part of outgoing command: %r" % self.outgoing
            sent = self.sock.send(self.outgoing)
            print "Sent %d bytes out of %d" % (sent, len(self.outgoing))
            if sent < len(self.outgoing):
                self.outgoing = self.outgoing[sent:]
                print "Next time we'll try to write: %r" % outgoing
            else:
                print "Done sending last command"
                self.outgoing = None
        if xlist:
            print "Hmm, exceptional condition raised?"

    def run(self):
        if self.sock is None:
            raise IOError("Socket is not connected, use open() first")
        while True:
            self._run_onetime()

    def open(self):
        if self.sock is not None:
            raise IOError("Socket is already connected")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(self.addr)
        self.sock.setblocking(0)

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None


def main(addr):
    nso = NetworkSerialController(addr)
    nso.open()
    #cmds.put("reboot\n") # just for testing
    try:
        print "Entering infinite loop, press ctrl+c to exit"
        nso.run()
    except KeyboardInterrupt:
        print "Shutting down"
    finally:
        nso.close()


if __name__ == "__main__":
    main(("127.0.0.1", 7777))
