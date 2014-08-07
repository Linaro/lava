def run_tests():
    from django_testproject.tests import run_tests_for
    # test last two items in INSTALLED APPS
    return run_tests_for("linaro_django_xmlrpc.test_project.settings", -2)


if __name__ == '__main__':
    run_tests()
