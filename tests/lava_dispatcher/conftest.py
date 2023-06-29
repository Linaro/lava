#  Copyright 2023 Collabora Limited
#  Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later


def pytest_addoption(parser):
    parser.addini("DJANGO_SETTINGS_MODULE", "LAVA dispatcher test warning silence")
