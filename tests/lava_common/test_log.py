# Copyright (C) 2020 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import logging

from lava_common.log import HTTPHandler, YAMLLogger, sender
from lava_common.yaml import yaml_safe_load


def test_sender(mocker):
    response = mocker.Mock(status_code=200)
    response.json = mocker.Mock(side_effect=[{"line_count": 1000}, {"line_count": 1}])
    post = mocker.Mock(return_value=response)
    enter = mocker.MagicMock()
    enter.__enter__ = mocker.Mock(return_value=mocker.Mock(post=post))
    session = mocker.MagicMock(return_value=enter)

    mocker.patch("requests.Session", session)
    conn = mocker.MagicMock()
    conn.poll = mocker.MagicMock()
    conn.recv_bytes = mocker.MagicMock()
    conn.recv_bytes.side_effect = [f"{i:04}".encode() for i in range(0, 1001)] + [b""]

    sender(conn, "http://localhost", "my-token", 1)
    assert len(conn.poll.mock_calls) == 2000
    assert len(conn.recv_bytes.mock_calls) == 1002

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


def test_sender_exceptions(mocker):
    response = mocker.Mock(status_code=200)
    response.json = mocker.Mock(
        side_effect=[{}, {"line_count": "s"}, {"line_count": 1}]
    )
    post = mocker.Mock(return_value=response)
    enter = mocker.MagicMock()
    enter.__enter__ = mocker.Mock(return_value=mocker.Mock(post=post))
    session = mocker.MagicMock(return_value=enter)

    mocker.patch("requests.Session", session)
    conn = mocker.MagicMock()
    conn.poll = mocker.MagicMock()
    conn.recv_bytes = mocker.MagicMock()
    conn.recv_bytes.side_effect = [b"hello world", b""]

    sender(conn, "http://localhost", "my-token", 1)
    assert len(post.mock_calls) == 3
    for c in post.mock_calls:
        assert c[1] == ("http://localhost",)
        assert c[2]["data"] == {"lines": "- hello world", "index": 0}


def test_http_handler(mocker):
    Process = mocker.Mock()
    mocker.patch("multiprocessing.Process", return_value=Process)
    mocker.patch("multiprocessing.Pipe", return_value=(mocker.Mock(), mocker.Mock()))
    handler = HTTPHandler("http://localhost/", "token", 1)

    assert len(Process.start.mock_calls) == 1
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

    assert len(handler.writer.send_bytes.mock_calls) == 1
    assert handler.writer.send_bytes.mock_calls[0][1] == (b"Hello world",)

    handler.close()
    assert len(handler.writer.send_bytes.mock_calls) == 2
    assert handler.writer.send_bytes.mock_calls[1][1] == (b"",)


def test_yaml_logger(mocker):
    mocker.patch("multiprocessing.Process")

    logger = YAMLLogger("lava")
    assert logger.handler is None
    logger.addHTTPHandler("http://localhost/", "my-token", 1)
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
