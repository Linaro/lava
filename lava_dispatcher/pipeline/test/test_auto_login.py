from lava_dispatcher.pipeline.action import JobError, Pipeline
from lava_dispatcher.pipeline.actions.boot import AutoLoginAction
from lava_dispatcher.pipeline.test.test_basic import StdoutTestCase


class AutoLoginTestCase(StdoutTestCase):

    def _make_pipeline(self, params):
        pipeline = Pipeline()
        auto_login = AutoLoginAction()
        auto_login.section = "internal"
        auto_login.parameters = params
        pipeline.add_action(auto_login)
        return pipeline

    def _check_errors(self, params, errors):
        pipeline = self._make_pipeline(params)
        self.assertRaises(JobError, pipeline.validate_actions)
        self.assertEqual(pipeline.errors, errors)

    def _check_valid(self, params):
        pipeline = self._make_pipeline(params)
        try:
            pipeline.validate_actions()
        except JobError as e:
            self.fail(str(e))

    def test_no_prompts(self):
        self._check_errors({},
                           ["'prompts' is mandatory for AutoLoginAction",
                            "'prompts' should be a list or a str",
                            "Value for 'prompts' cannot be empty"])

    def test_prompts(self):
        self._check_valid({'prompts': 'hello'})
        self._check_errors({'prompts': True},
                           ["'prompts' should be a list or a str"])
        self._check_errors({'prompts': ''},
                           ["Value for 'prompts' cannot be empty"])
        self._check_errors({'prompts': ['hello', '']},
                           ["Items of 'prompts' can't be empty"])

    def test_dict(self):
        self._check_errors({'prompts': 'hello', 'auto_login': True},
                           ["'auto_login' should be a dictionary"])

    def test_login_prompt(self):
        self._check_errors({'prompts': 'hello', 'auto_login': {None: None}},
                           ["'login_prompt' is mandatory for auto_login",
                            "'username' is mandatory for auto_login"])
        self._check_errors({'prompts': 'hello',
                            'auto_login': {
                                'login_prompt': '',
                                'username': 'bob',
                            }},
                           ["Value for 'login_prompt' cannot be empty"])
        self._check_valid({'prompts': 'hello',
                           'auto_login': {
                               'login_prompt': 'login:',
                               'username': 'bob',
                           }})

    def test_password_prompt(self):
        self._check_errors({'prompts': 'hello',
                            'auto_login': {
                                'login_prompt': 'login:',
                                'username': 'bob',
                                'password_prompt': 'pass:',
                            }},
                           ["'password' is mandatory if 'password_prompt' is used in auto_login"])
        self._check_valid({'prompts': 'hello',
                           'auto_login': {
                               'login_prompt': 'login:',
                               'username': 'bob',
                               'password_prompt': 'pass:',
                               'password': 'abc',
                           }})

    def test_login_commands(self):
        auto_login = {
            'login_prompt': 'login:',
            'username': 'bob',
        }

        auto_login['login_commands'] = None
        self._check_errors({'prompts': 'hello', 'auto_login': auto_login},
                           ["'login_commands' must be a list",
                            "'login_commands' must not be empty"])
        auto_login['login_commands'] = 'su'
        self._check_errors({'prompts': 'hello', 'auto_login': auto_login},
                           ["'login_commands' must be a list"])
        auto_login['login_commands'] = []
        self._check_errors({'prompts': 'hello', 'auto_login': auto_login},
                           ["'login_commands' must not be empty"])
        auto_login['login_commands'] = ['sudo su']
        self._check_valid({'prompts': 'hello', 'auto_login': auto_login})
