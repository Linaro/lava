# Copyright (c) 2010 Linaro
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Unit tests for launch_control.utils.registry module
"""

from unittest import TestCase

from launch_control.utils.registry import RegistryBase


class AutoRegisterTypeTestCase(TestCase):
    def test_registeration(self):
        class A(RegistryBase):
            pass
        self.assertEqual(A.get_direct_subclasses(), [])
        self.assertEqual(A.get_subclasses(), [])
        class B(A):
            pass
        self.assertEqual(A.get_direct_subclasses(), [B])
        self.assertEqual(A.get_subclasses(), [B])
        self.assertEqual(B.get_direct_subclasses(), [])
        self.assertEqual(B.get_subclasses(), [])
        class C(B):
            pass
        self.assertEqual(A.get_direct_subclasses(), [B])
        self.assertEqual(A.get_subclasses(), [B, C])
        self.assertEqual(B.get_direct_subclasses(), [C])
        self.assertEqual(B.get_subclasses(), [C])
        self.assertEqual(C.get_direct_subclasses(), [])
        self.assertEqual(C.get_subclasses(), [])
