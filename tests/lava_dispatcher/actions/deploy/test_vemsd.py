from unittest.mock import MagicMock

from lava_dispatcher.actions.deploy.vemsd import EnterVExpressMCC

from ...test_basic import LavaDispatcherTestCase


class TestEnterVExpressMCC(LavaDispatcherTestCase):
    def test_send_interrupt_char_with_delay(self):
        job = self.create_simple_job(
            device_dict={
                "character_delays": {"deploy": 30},
                "actions": {
                    "deploy": {
                        "methods": {
                            "vemsd": {
                                "parameters": {
                                    "interrupt_char": " ",
                                    "mcc_prompt": "Cmd>",
                                    "autorun_prompt": "Hit key to stop autoboot",
                                    "mcc_reset_msg": "MCC Reset",
                                }
                            }
                        }
                    }
                },
            }
        )
        action = EnterVExpressMCC(job)
        action.section = "deploy"
        action.parameters = {"namespace": "common"}
        action.validate()

        connection = MagicMock()
        action.wait = MagicMock(side_effect=[0, 0])

        action.run(connection, max_end_time=10)

        connection.sendline.assert_called_once_with(" ", 30)
