# Copyright (C) 2020 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import logging
import signal

from lava_common.log import HTTPHandler, JobOutputSender, YAMLListFormatter, YAMLLogger
from lava_common.yaml import yaml_safe_load


def test_sender(mocker, capsys):
    response = mocker.Mock(status_code=200)
    response.json = mocker.Mock(side_effect=[{"line_count": 1000}, {"line_count": 1}])
    post = mocker.Mock(return_value=response)
    session = mocker.MagicMock(
        return_value=mocker.MagicMock(
            post=post,
        )
    )
    mocker.patch("requests.Session", session)

    conn = mocker.MagicMock()
    conn.get.side_effect = ["0000", "1000"]
    conn.get_nowait.side_effect = [f"{i:04}" for i in range(1, 1000)] + [None]

    JobOutputSender(conn, "http://localhost", "my-token", 1, "1234").run()

    assert len(conn.get.mock_calls) == 2
    assert conn.get.mock_calls[0] == mocker.call(block=True, timeout=1)
    assert conn.get.mock_calls[1] == mocker.call(block=True, timeout=1)
    assert len(conn.get_nowait.mock_calls) == 1000

    assert len(post.mock_calls) == 2
    assert post.mock_calls[0][1] == ("http://localhost",)
    assert post.mock_calls[1][1] == ("http://localhost",)
    assert post.mock_calls[0][2]["data"] == {
        "lines": "- " + "\n- ".join([f"{i:04}" for i in range(0, 1000)]),
        "index": 0,
    }
    assert post.mock_calls[1][2]["data"] == {"lines": "- 1000", "index": 1000}
    assert post.mock_calls[0][2]["headers"]["LAVA-Token"] == "my-token"
    assert post.mock_calls[1][2]["headers"]["LAVA-Token"] == "my-token"

    out, _ = capsys.readouterr()
    assert "INFO [LOGGER] POST: total records sent: 1000" in out
    assert "INFO [LOGGER] POST: total records sent: 1001" in out


def test_sender_exceptions(mocker):
    response = mocker.Mock(status_code=200)
    response.json = mocker.Mock(
        side_effect=[{}, {"line_count": "s"}, {"line_count": 1}]
    )
    post = mocker.Mock(return_value=response)
    session = mocker.MagicMock(
        return_value=mocker.MagicMock(
            post=post,
        )
    )
    mocker.patch("requests.Session", session)

    conn = mocker.MagicMock()
    conn.get.side_effect = ["hello world"]
    conn.get_nowait.side_effect = [None]

    JobOutputSender(conn, "http://localhost", "my-token", 1, "1234").run()
    assert len(post.mock_calls) == 3
    for c in post.mock_calls:
        assert c[1] == ("http://localhost",)
        assert c[2]["data"] == {"lines": "- hello world", "index": 0}


def test_sender_404(mocker, capsys):
    job_id = "123"
    response = mocker.Mock(status_code=404)
    response.json.return_value = {"error": f"Unknown job '{job_id}'"}
    post = mocker.Mock(return_value=response)
    session = mocker.MagicMock(
        return_value=mocker.MagicMock(
            post=post,
        )
    )
    mocker.patch("requests.Session", session)

    conn = mocker.MagicMock()
    os_getppid = mocker.patch("os.getppid", return_value=1)
    os_kill = mocker.patch("os.kill")

    sender = JobOutputSender(
        conn,
        f"http://localhost/scheduler/internal/v1/jobs/{job_id}/logs/",
        "my-token",
        1,
        job_id,
    )
    sender.records = ["hello world"]
    sender.post()

    os_getppid.assert_called_once()
    os_kill.assert_called_once_with(1, signal.SIGUSR1)

    _, err = capsys.readouterr()
    assert "ERROR [LOGGER] POST: 404 - " in err


def test_sender_413(mocker, capsys):
    response = mocker.Mock(status_code=413)
    post = mocker.Mock(return_value=response)
    session = mocker.MagicMock(
        return_value=mocker.MagicMock(
            post=post,
        )
    )
    mocker.patch("requests.Session", session)

    conn = mocker.MagicMock()
    sender = JobOutputSender(
        conn,
        "http://localhost/scheduler/internal/v1/jobs/123/logs/",
        "my-token",
        1,
        "123",
    )

    # Test records are too large to upload
    sender.max_records = 1000
    sender.records = ["hello world"]
    initial_max_records = sender.max_records
    sender.post()
    assert sender.max_records == initial_max_records - 100

    # Test single record is still too large to upload
    sender.max_records = 1
    sender.records = ["very long single record line that exceeds server limits"]
    sender.post()
    assert len(sender.records) == 1
    replaced_record = yaml_safe_load(sender.records[0])
    assert replaced_record["lvl"] == "results"
    assert replaced_record["msg"] == {
        "definition": "lava",
        "case": "log-upload",
        "result": "fail",
    }

    _, err = capsys.readouterr()
    assert "ERROR [LOGGER] POST: 413 - " in err


def test_http_handler(mocker):
    Process = mocker.Mock()
    Queue = mocker.Mock()
    mocker.patch("multiprocessing.Process", return_value=Process)
    mocker.patch("multiprocessing.Queue", return_value=Queue)
    handler = HTTPHandler("http://localhost/", "token", 1, "1234")

    assert len(Process.start.mock_calls) == 1

    record = logging.LogRecord(
        name="lava",
        level=logging.ERROR,
        lineno=0,
        pathname=None,
        msg="Hello world",
        args=None,
        exc_info=None,
    )
    handler.emit(record)
    record = logging.LogRecord(
        name="lava",
        level=logging.ERROR,
        lineno=0,
        pathname=None,
        msg="",
        args=None,
        exc_info=None,
    )
    handler.emit(record)

    assert len(handler.queue.put.mock_calls) == 1
    assert handler.queue.put.mock_calls[0][1] == ("Hello world",)

    handler.close()
    assert len(handler.queue.put.mock_calls) == 2
    assert handler.queue.put.mock_calls[1][1] == (None,)


def test_yaml_logger(mocker):
    mocker.patch("multiprocessing.Process")

    logger = YAMLLogger("lava")
    assert logger.handler is None
    logger.addHTTPHandler("http://localhost/", "my-token", 1, "1234")
    assert isinstance(logger.handler, HTTPHandler) is True

    def check(logger, lvl, lvlno, msg=None, mock_calls=1):
        assert len(logger._log.mock_calls) == mock_calls
        if mock_calls == 0:
            return
        assert logger._log.mock_calls[0][1][0] == lvlno
        data = yaml_safe_load(logger._log.mock_calls[0][1][1])
        if lvl == "feedback":
            assert list(data.keys()) == ["dt", "lvl", "msg", "ns"]
        else:
            assert list(data.keys()) == ["dt", "lvl", "msg"]
        assert data["lvl"] == lvl
        if msg is None:
            assert data["msg"] == f"an {lvl}"
        else:
            assert data["msg"] == msg

    logger._log = mocker.Mock()
    logger.exception("an exception")
    check(logger, "exception", logging.ERROR)

    logger._log = mocker.Mock()
    logger.error("an error: %d", 1)
    check(logger, "error", logging.ERROR, "an error: 1")

    logger._log = mocker.Mock()
    logger.warning("a warning")
    check(logger, "warning", logging.WARNING, "a warning")

    logger._log = mocker.Mock()
    logger.info("an info")
    check(logger, "info", logging.INFO)

    logger._log = mocker.Mock()
    logger.debug("a debug message")
    check(logger, "debug", logging.DEBUG, "a debug message")

    logger._log = mocker.Mock()
    logger.input("an input")
    check(logger, "input", logging.INFO)

    logger._log = mocker.Mock()
    logger.target("a target message")
    check(logger, "target", logging.INFO, "a target message")

    logger._log = mocker.Mock()
    logger.feedback("a feedback from namespace", namespace="ns")
    check(logger, "feedback", logging.INFO, "a feedback from namespace")

    logger._log = mocker.Mock()
    logger.marker({"case": "0_test", "type": "start_test_case"})
    check(
        logger, "marker", logging.INFO, {"case": "0_test", "type": "start_test_case"}, 0
    )

    logger.event("an event")
    check(logger, "event", logging.INFO)

    logger.marker({"case": "0_test", "type": "end_test_case"})
    assert len(logger._log.mock_calls) == 1
    assert logger.markers == {"0_test": {"start_test_case": 7, "end_test_case": 8}}

    logger._log = mocker.Mock()
    logger.info("a" * 10**7)
    check(logger, "info", logging.INFO, "<line way too long ...>")

    logger.close()
    assert logger.handler is None


def test_yaml_list_formatter():
    formatter = YAMLListFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)
    assert formatted == "- test message"
