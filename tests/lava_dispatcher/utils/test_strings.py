from lava_dispatcher.utils.strings import (
    indices,
    map_kernel_uboot,
    seconds_to_str,
    substitute,
)


def test_indices():
    assert indices("abcdeabcdea", "a") == [0, 5, 10]
    assert indices("abcdeabcdea", "q") == []


def test_substitute():
    assert substitute(["hello", "world"], {}) == ["hello", "world"]
    assert substitute(["hello", "world"], {"hello": "strange"}) == ["strange", "world"]
    assert substitute(["hello", "world"], {"nice": "strange"}) == ["hello", "world"]
    assert substitute(["hello", "world"], {"nice": "strange"}, drop=True) == [
        "hello",
        "world",
    ]
    assert substitute(["hello", "world"], {"hello": None}) == ["hello", "world"]
    assert substitute(["hello", "world"], {"hello": None}, drop=True) == ["world"]
    assert substitute(
        ["hello", "world"], {"hello": None}, drop=True, drop_line=False
    ) == ["world"]


def test_seconds_to_str():
    assert seconds_to_str(0) == "00:00:00"
    assert seconds_to_str(1) == "00:00:01"
    assert seconds_to_str(62) == "00:01:02"
    assert seconds_to_str(147) == "00:02:27"
    assert seconds_to_str(3641) == "01:00:41"


def test_map_kernel_uboot():
    assert map_kernel_uboot("uimage", {}) == "bootm"
    assert map_kernel_uboot("zimage", {}) == "bootm"
    assert map_kernel_uboot("zimage", {"bootz": None}) == "bootz"
    assert map_kernel_uboot("image", {}) == "bootm"
    assert map_kernel_uboot("image", {"booti": None}) == "booti"
