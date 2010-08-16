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
