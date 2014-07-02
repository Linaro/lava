"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

from django.test import TestCase

from linaro_django_xmlrpc.test_project.example.models import ExampleAPI


class ExampleAPITestCase(TestCase):

    def test_foo(self):
        obj = ExampleAPI()
        retval = obj.foo()
        self.assertEqual(retval, "bar")
