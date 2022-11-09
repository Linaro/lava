import signal
import time

import pytest

from lava_common.exceptions import ConfigurationError, InfrastructureError, JobError
from lava_common.timeout import Timeout


class DummyAlarm:
    def __init__(self, data):
        self.data = data
        self.previous = 0

    def __call__(self, duration):
        assert (  # nosec - assert is part of the test process.
            self.data.pop(0) == duration
        )
        previous = self.previous
        self.previous = duration
        return previous


class DummySignal:
    def __init__(self, data):
        self.data = data
        self.previous = 0

    def __call__(self, sig, func):
        assert sig == signal.SIGALRM  # nosec - assert is part of the test process.
        assert func == self.data.pop(0)  # nosec - assert is part of the test process.
        previous = self.previous
        self.previous = func
        return previous


class ParentAction:
    def __init__(self, timeout):
        self.timeout = timeout


def test_parsing():
    # 1/ simple durations
    assert (  # nosec - assert is part of the test process.
        Timeout.parse({"days": 1}) == 86400
    )
    assert (  # nosec - assert is part of the test process.
        Timeout.parse({"hours": 3}) == 3 * 3600
    )
    assert (  # nosec - assert is part of the test process.
        Timeout.parse({"minutes": 1}) == 1 * 60
    )
    assert (  # nosec - assert is part of the test process.
        Timeout.parse({"seconds": 345}) == 345
    )

    # 2/ complexe durations
    assert (  # nosec - assert is part of the test process.
        Timeout.parse({"minutes": 22, "seconds": 17}) == 22 * 60 + 17
    )
    assert (  # nosec - assert is part of the test process.
        Timeout.parse({"hours": 2, "minutes": 22, "seconds": 17})
        == 2 * 3600 + 22 * 60 + 17
    )
    assert (  # nosec - assert is part of the test process.
        Timeout.parse({"days": 1, "minutes": 22, "seconds": 17}) == 86400 + 22 * 60 + 17
    )

    # 3/ invalid durations
    assert (  # nosec - assert is part of the test process.
        Timeout.parse({"day": 1}) == Timeout.default_duration()
    )
    assert (  # nosec - assert is part of the test process.
        Timeout.parse({}) == Timeout.default_duration()
    )

    with pytest.raises(ConfigurationError):
        Timeout.parse("")


def test_exception_raised(monkeypatch):
    # 1/ default case
    t = Timeout("name", 12)
    monkeypatch.setattr(signal, "signal", DummySignal([t._timed_out]))
    monkeypatch.setattr(signal, "alarm", DummyAlarm([12, 0]))
    with pytest.raises(JobError):
        with t(None, None) as max_end_time:
            t._timed_out(None, None)

    # 2/ another exception
    t = Timeout("name", 12, InfrastructureError)
    monkeypatch.setattr(signal, "signal", DummySignal([t._timed_out]))
    monkeypatch.setattr(signal, "alarm", DummyAlarm([12, 0]))
    with pytest.raises(InfrastructureError):
        with t(None, None) as max_end_time:
            t._timed_out(None, None)


def test_without_raising(monkeypatch):
    # 1/ without parent
    # 1.1/ without max_end_time
    t = Timeout("timeout-name", 200)
    monkeypatch.setattr(signal, "signal", DummySignal([t._timed_out]))
    monkeypatch.setattr(signal, "alarm", DummyAlarm([200, 0]))
    monkeypatch.setattr(time, "monotonic", lambda: 0)
    with t(None, None) as max_end_time:
        assert max_end_time == 200  # nosec - assert is part of the test process.
        # signal.alarm and signal.signal were called once each
        assert signal.alarm.data == [0]  # nosec - assert is part of the test process.
        assert signal.signal.data == []  # nosec - assert is part of the test process.
        monkeypatch.setattr(time, "monotonic", lambda: 23)
    assert signal.alarm.data == []  # nosec - assert is part of the test process.
    assert t.elapsed_time == 23  # nosec - assert is part of the test process.

    # 1.1/ with a smaller max_end_time
    t = Timeout("timeout-name", 200)
    monkeypatch.setattr(signal, "signal", DummySignal([t._timed_out]))
    monkeypatch.setattr(signal, "alarm", DummyAlarm([125, 0]))
    monkeypatch.setattr(time, "monotonic", lambda: 0)
    with t(None, 125) as max_end_time:
        assert max_end_time == 125  # nosec - assert is part of the test process.
        assert signal.alarm.data == [0]  # nosec - assert is part of the test process.
        assert signal.signal.data == []  # nosec - assert is part of the test process.
        monkeypatch.setattr(time, "monotonic", lambda: 109)
    assert signal.alarm.data == []  # nosec - assert is part of the test process.
    assert t.elapsed_time == 109  # nosec - assert is part of the test process.

    # 1.2/ with a larger max_end_time
    t = Timeout("timeout-name", 200)
    monkeypatch.setattr(signal, "signal", DummySignal([t._timed_out]))
    monkeypatch.setattr(signal, "alarm", DummyAlarm([200, 0]))
    monkeypatch.setattr(time, "monotonic", lambda: 0)
    with t(None, 201) as max_end_time:
        assert max_end_time == 200  # nosec - assert is part of the test process.
        assert signal.alarm.data == [0]  # nosec - assert is part of the test process.
        assert signal.signal.data == []  # nosec - assert is part of the test process.
        monkeypatch.setattr(time, "monotonic", lambda: 45)
    assert signal.alarm.data == []  # nosec - assert is part of the test process.
    assert t.elapsed_time == 45  # nosec - assert is part of the test process.

    # 2/ with a parent
    # 2.1/ with a larger max_end_time
    t0 = Timeout("timeout-parent", 200)
    parent = ParentAction(t0)
    t1 = Timeout("timeout-child", 100)
    monkeypatch.setattr(signal, "signal", DummySignal([t1._timed_out, t0._timed_out]))
    monkeypatch.setattr(signal, "alarm", DummyAlarm([100, 177]))
    monkeypatch.setattr(time, "monotonic", lambda: 0)
    with t1(parent, 200) as max_end_time:
        assert max_end_time == 100  # nosec - assert is part of the test process.
        assert signal.alarm.data == [177]  # nosec - assert is part of the test process.
        assert signal.signal.data == [  # nosec - assert is part of the test process.
            t0._timed_out
        ]
        monkeypatch.setattr(time, "monotonic", lambda: 23)
    assert signal.alarm.data == []  # nosec - assert is part of the test process.
    assert t1.elapsed_time == 23  # nosec - assert is part of the test process.

    # 2.2/ with a smaller max_end_time
    t0 = Timeout("timeout-parent", 50)
    parent = ParentAction(t0)
    t1 = Timeout("timeout-child", 100)
    monkeypatch.setattr(signal, "signal", DummySignal([t1._timed_out, t0._timed_out]))
    monkeypatch.setattr(signal, "alarm", DummyAlarm([50, 27]))
    monkeypatch.setattr(time, "monotonic", lambda: 0)
    with t1(parent, 50) as max_end_time:
        assert max_end_time == 50  # nosec - assert is part of the test process.
        assert signal.alarm.data == [27]  # nosec - assert is part of the test process.
        assert signal.signal.data == [  # nosec - assert is part of the test process.
            t0._timed_out
        ]
        monkeypatch.setattr(time, "monotonic", lambda: 23)
    assert signal.alarm.data == []  # nosec - assert is part of the test process.
    assert t1.elapsed_time == 23  # nosec - assert is part of the test process.


def test_with_raising(monkeypatch):
    # 1/ without parent
    # 1.1/ without max_end_time
    t = Timeout("timeout-name", 200)
    monkeypatch.setattr(signal, "signal", DummySignal([t._timed_out]))
    monkeypatch.setattr(signal, "alarm", DummyAlarm([200, 0]))
    monkeypatch.setattr(time, "monotonic", lambda: 0)
    with pytest.raises(JobError):
        with t(None, None) as max_end_time:
            assert max_end_time == 200  # nosec - assert is part of the test process.
            assert signal.alarm.data == [  # nosec - assert is part of the test process.
                0
            ]
            assert (  # nosec - assert is part of the test process.
                signal.signal.data == []
            )
            monkeypatch.setattr(time, "monotonic", lambda: 200)
            t._timed_out(None, None)
    assert signal.alarm.data == []  # nosec - assert is part of the test process.
    assert t.elapsed_time == 200  # nosec - assert is part of the test process.

    # 1.1/ with a smaller max_end_time
    t = Timeout("timeout-name", 200)
    monkeypatch.setattr(signal, "signal", DummySignal([t._timed_out]))
    monkeypatch.setattr(signal, "alarm", DummyAlarm([125, 0]))
    monkeypatch.setattr(time, "monotonic", lambda: 0)
    with pytest.raises(JobError):
        with t(None, 125) as max_end_time:
            assert max_end_time == 125  # nosec - assert is part of the test process.
            assert signal.alarm.data == [  # nosec - assert is part of the test process.
                0
            ]
            assert (  # nosec - assert is part of the test process.
                signal.signal.data == []
            )
            monkeypatch.setattr(time, "monotonic", lambda: 126)
            t._timed_out(None, None)
    assert signal.alarm.data == []  # nosec - assert is part of the test process.
    assert t.elapsed_time == 126  # nosec - assert is part of the test process.

    # 1.2/ with a larger max_end_time
    t = Timeout("timeout-name", 200)
    monkeypatch.setattr(signal, "signal", DummySignal([t._timed_out]))
    monkeypatch.setattr(signal, "alarm", DummyAlarm([200, 0]))
    monkeypatch.setattr(time, "monotonic", lambda: 0)
    with pytest.raises(JobError):
        with t(None, 201) as max_end_time:
            assert max_end_time == 200  # nosec - assert is part of the test process.
            assert signal.alarm.data == [0]  # nosec - test process.
            assert signal.signal.data == []  # nosec - test process.
            monkeypatch.setattr(time, "monotonic", lambda: 200)
            t._timed_out(None, None)
    assert signal.alarm.data == []  # nosec - assert is part of the test process.
    assert t.elapsed_time == 200  # nosec - assert is part of the test process.

    # 1.3/ with max_end_time <= 0
    t = Timeout("timeout-name", 200)
    monkeypatch.setattr(signal, "signal", DummySignal([t._timed_out]))
    monkeypatch.setattr(signal, "alarm", DummyAlarm([0]))
    monkeypatch.setattr(time, "monotonic", lambda: 0)
    with pytest.raises(JobError):
        with t(None, 0) as max_end_time:
            # Check that the exception is raised before this line
            assert 0  # nosec - assert is part of the test process.
    assert signal.alarm.data == []  # nosec - assert is part of the test process.
    assert t.elapsed_time == 0  # nosec - assert is part of the test process.

    # 2/ with a parent
    # 2.1/ with a larger max_end_time
    t0 = Timeout("timeout-parent", 200)
    parent = ParentAction(t0)
    t1 = Timeout("timeout-child", 100)
    monkeypatch.setattr(signal, "signal", DummySignal([t1._timed_out, t0._timed_out]))
    monkeypatch.setattr(signal, "alarm", DummyAlarm([100, 0]))
    monkeypatch.setattr(time, "monotonic", lambda: 0)
    with pytest.raises(JobError):
        with t1(parent, 200) as max_end_time:
            assert max_end_time == 100  # nosec - assert is part of the test process.
            assert signal.alarm.data == [0]  # nosec - test process.
            assert signal.signal.data == [t0._timed_out]  # nosec - test process.
            monkeypatch.setattr(time, "monotonic", lambda: 100)
            t1._timed_out(None, None)
    assert signal.alarm.data == []  # nosec - assert is part of the test process.
    assert signal.signal.data == [t0._timed_out]  # nosec - test process.
    assert t1.elapsed_time == 100  # nosec - assert is part of the test process.

    # 2.2/ with a smaller max_end_time
    t0 = Timeout("timeout-parent", 50)
    parent = ParentAction(t0)
    t1 = Timeout("timeout-child", 100)
    monkeypatch.setattr(signal, "signal", DummySignal([t1._timed_out, t0._timed_out]))
    monkeypatch.setattr(signal, "alarm", DummyAlarm([50, 0]))
    monkeypatch.setattr(time, "monotonic", lambda: 0)
    with pytest.raises(JobError):
        with t1(parent, 50) as max_end_time:
            assert max_end_time == 50  # nosec - assert is part of the test process.
            assert signal.alarm.data == [0]  # nosec - test process.
            assert signal.signal.data == [t0._timed_out]  # nosec - test process.
            monkeypatch.setattr(time, "monotonic", lambda: 23)
            t1._timed_out(None, None)
    assert signal.alarm.data == []  # nosec - assert is part of the test process.
    assert signal.signal.data == [t0._timed_out]  # nosec - test process.
    assert t1.elapsed_time == 23  # nosec - assert is part of the test process.

    # 2.3/ with max_end_time <= 0
    t0 = Timeout("timeout-parent", 1)
    parent = ParentAction(t0)
    t1 = Timeout("timeout-child", 100)
    monkeypatch.setattr(signal, "signal", DummySignal([t1._timed_out, t0._timed_out]))
    monkeypatch.setattr(signal, "alarm", DummyAlarm([0]))
    monkeypatch.setattr(time, "monotonic", lambda: 0)
    with pytest.raises(JobError):
        with t1(parent, -1) as max_end_time:
            assert 0  # nosec - assert is part of the test process.
    assert signal.alarm.data == []  # nosec - assert is part of the test process.
    assert signal.signal.data == [t1._timed_out, t0._timed_out]  # nosec - test process.
    assert t1.elapsed_time == 0  # nosec - assert is part of the test process.

    # 2.4/ raising parent timeout
    t0 = Timeout("timeout-parent", 50, InfrastructureError)
    parent = ParentAction(t0)
    t1 = Timeout("timeout-child", 100)
    monkeypatch.setattr(signal, "signal", DummySignal([t1._timed_out, t0._timed_out]))
    monkeypatch.setattr(signal, "alarm", DummyAlarm([50, 0, 0]))
    monkeypatch.setattr(time, "monotonic", lambda: 0)
    with pytest.raises(InfrastructureError):
        with t1(parent, 50) as max_end_time:
            assert max_end_time == 50  # nosec - assert is part of the test process.
            assert signal.alarm.data == [0, 0]  # nosec - test
            assert signal.signal.data == [t0._timed_out]  # nosec - test
            monkeypatch.setattr(time, "monotonic", lambda: 50)
    assert signal.alarm.data == []  # nosec - assert is part of the test process.
    assert signal.signal.data == []  # nosec - assert is part of the test process.
    assert t1.elapsed_time == 50  # nosec - assert is part of the test process.
