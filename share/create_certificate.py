#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  Copyright 2016 Rémi Duraffort <remi.duraffort@linaro.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#

import argparse
import zmq.auth


def main():
    """
    Parse options and create the certificate
    """
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--directory", type=str,
                        default="/etc/lava-dispatcher/certificates.d",
                        help="Directory where to store the certificates")
    parser.add_argument(type=str, dest="name",
                        help="Name of the certificate")
    args = parser.parse_args()

    # Create the certificate
    print("Creating the certificate in %s" % args.directory)
    zmq.auth.create_certificates(args.directory, args.name)
    print(" - %s.key" % args.name)
    print(" - %s.key_secret" % args.name)


if __name__ == '__main__':
    main()
