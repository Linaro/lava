import os
import time
from unittest.mock import MagicMock, patch

from lava_common.constants import DISPATCHER_DOWNLOAD_DIR
from lava_dispatcher.actions.boot import OverlayUnpack
from tests.lava_dispatcher.test_basic import LavaDispatcherTestCase


class TestOverlayZmodem(LavaDispatcherTestCase):
    @patch("subprocess.run")
    def test_zmodem_overlay_transfer(self, mock_run):
        # Prepare job with device uart
        job = self.create_simple_job(
            device_dict={"device_info": [{"uart": "/dev/ttyUSB0"}]}
        )

        action = OverlayUnpack(job)
        action.parameters = {
            "namespace": "common",
            "transfer_overlay": {
                "transfer_method": "zmodem",
                "unpack_command": "tar -xzf",
            },
        }

        # Prepare namespace data expected by the action
        overlay_full_path = os.path.join(
            DISPATCHER_DOWNLOAD_DIR, "tmp", "overlay.tar.gz"
        )
        action.set_namespace_data(
            action="compress-overlay",
            label="output",
            key="file",
            value=overlay_full_path,
        )

        # Setup fake connection
        class Connection:
            def __init__(self):
                self.connected = True
                self.prompt_str = []
                self.raw_connection = MagicMock()
                self.raw_connection.linesep = "\n"
                self._send_calls = []

            def sendline(self, cmd, delay=0, check=False, timeout=None):
                self._send_calls.append(cmd)

            def wait(self, max_end_time=None):
                return 0

        conn = Connection()

        # Run action
        mock_run.return_value = MagicMock(returncode=0)
        res_conn = action.run(conn, max_end_time=time.monotonic() + 5)

        # Verify subprocess.run was called to execute sz with overlay path and uart
        assert mock_run.called
        called_arg = mock_run.call_args[0][0]
        assert str(overlay_full_path) in called_arg
        assert "/dev/ttyUSB0" in called_arg

        # Verify rz was sent and unpack command executed on device
        assert conn._send_calls[0] == "rz"
        # unpack command should include the overlay basename
        assert "tar -xzf" in conn._send_calls[1]
