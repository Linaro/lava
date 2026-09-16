# Copyright (C) 2026 Linaro Limited
#
# Author: Ben Copeland <ben.copeland@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import re
from pathlib import Path

import pytest

APACHE_CONFIG = Path(__file__).resolve().parents[2] / "etc/lava-server.conf"

EXPECTED_MEDIA_TYPES = {
    "css": '"text/css; charset=utf-8"',
    "eot": "application/vnd.ms-fontobject",
    "html": '"text/html; charset=utf-8"',
    "js": '"text/javascript; charset=utf-8"',
    "json": "application/json",
    "map": "application/json",
    "md": '"text/markdown; charset=utf-8"',
    "sh": "application/x-sh",
    "svg": "image/svg+xml",
    "ttf": "font/ttf",
    "txt": '"text/plain; charset=utf-8"',
    "xml": "application/xml",
    "yaml": "application/yaml",
}


@pytest.fixture
def apache_config():
    return "\n".join(
        line
        for line in APACHE_CONFIG.read_text().splitlines()
        if not line.lstrip().startswith("#")
    )


@pytest.fixture
def static_directory(apache_config):
    body = apache_config.split("<Directory /usr/share/lava-server/static>", 1)[1]
    return body.split("</Directory>", 1)[0]


def container_block(config, opening):
    body = config.split(opening, 1)[1]
    kind = opening.split()[0].lstrip("<")
    depth = 1
    lines = body.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"<{kind}"):
            depth += 1
        elif stripped.startswith(f"</{kind}>"):
            depth -= 1
            if depth == 0:
                return "\n".join(lines[:index])
    raise AssertionError(f"unterminated {opening}")


def without_containers(config, opening_prefix):
    while opening_prefix in config:
        start = config.index(opening_prefix)
        opening = config[start : config.index(">", start) + 1]
        inner = container_block(config[start:], opening)
        end = start + len(opening) + len(inner)
        end = config.index(">", config.index("</", end)) + 1
        config = config[:start] + config[end:]
    return config


def files_match_directives(config, filename):
    return "\n".join(
        body
        for pattern, body in re.findall(
            r'<FilesMatch "([^"]+)">(.*?)</FilesMatch>', config, re.DOTALL
        )
        if re.search(pattern, filename)
    )


def test_static_is_served_before_the_proxy(apache_config):
    assert apache_config.index("ProxyPass /static/ !") < apache_config.index(
        "ProxyPass / http://127.0.0.1:8000/"
    )
    assert "Alias /static/ /usr/share/lava-server/static/" in apache_config


def test_static_is_only_taken_off_gunicorn_when_headers_can_be_set(apache_config):
    guarded = container_block(apache_config, "<IfModule mod_headers.c>")
    assert "Alias /static/ /usr/share/lava-server/static/" in guarded
    assert "ProxyPass /static/ !" in guarded


def test_static_directory_options(static_directory):
    assert "Options +FollowSymLinks -Indexes" in static_directory
    assert "Require all granted" in static_directory


def test_headers_whitenoise_and_django_used_to_send(static_directory):
    assert 'Header set Cache-Control "max-age=60, public"' in static_directory
    assert "Header set X-Content-Type-Options nosniff" in static_directory
    assert 'Header set Access-Control-Allow-Origin "*"' in static_directory


def test_precompressed_files_are_not_compressed_again(static_directory):
    rewrite = container_block(static_directory, "<IfModule mod_rewrite.c>")
    assert re.search(r"RewriteRule\s+\\\.gz\$\s+-\s+\[E=no-gzip:1\]", rewrite)


def test_gzip_is_negotiated_on_accept_encoding_and_an_existing_file(static_directory):
    rewrite = container_block(static_directory, "<IfModule mod_rewrite.c>")
    assert "RewriteCond %{HTTP:Accept-Encoding} gzip" in rewrite
    assert "RewriteCond %{REQUEST_FILENAME}.gz -s" in rewrite


def test_rewrite_covers_exactly_the_documented_types(static_directory):
    pattern = re.search(r"RewriteRule \^\(\.\*\)\\\.\(([^)]+)\)\$", static_directory)
    assert pattern is not None
    assert set(pattern.group(1).split("|")) == set(EXPECTED_MEDIA_TYPES)


def test_precompressed_files_are_not_rewritten_again(static_directory):
    rule = re.search(r"RewriteRule (\^\S+) (\S+) (\S+)", static_directory)
    assert rule is not None
    pattern, replacement, flags = rule.groups()
    assert replacement == "$1.$2.gz"
    assert flags == "[QSA]"
    for extension in EXPECTED_MEDIA_TYPES:
        assert re.fullmatch(pattern, f"nested/asset.{extension}")
        assert not re.fullmatch(pattern, f"nested/asset.{extension}.gz")


def test_content_type_is_declared_and_does_not_depend_on_accept_encoding(
    static_directory,
):
    for extension, media_type in EXPECTED_MEDIA_TYPES.items():
        plain = re.findall(
            r"ForceType (.+)",
            files_match_directives(static_directory, f"a.{extension}"),
        )
        compressed = re.findall(
            r"ForceType (.+)",
            files_match_directives(static_directory, f"a.{extension}.gz"),
        )
        assert plain == [media_type], extension
        assert compressed == [media_type], extension


def test_content_encoding_is_set_only_on_compressed_files(static_directory):
    for extension in EXPECTED_MEDIA_TYPES:
        assert "Header set Content-Encoding gzip" in files_match_directives(
            static_directory, f"a.{extension}.gz"
        ), extension
        assert "Header set Content-Encoding gzip" not in files_match_directives(
            static_directory, f"a.{extension}"
        ), extension


def test_vary_is_set_on_both_representations(static_directory):
    for extension in EXPECTED_MEDIA_TYPES:
        for filename in (f"a.{extension}", f"a.{extension}.gz"):
            assert "Header set Vary Accept-Encoding" in files_match_directives(
                static_directory, filename
            ), filename


def test_content_types_apply_without_optional_modules(static_directory):
    unguarded = without_containers(static_directory, "<IfModule ")
    for extension, media_type in EXPECTED_MEDIA_TYPES.items():
        assert re.findall(
            r"ForceType (.+)", files_match_directives(unguarded, f"a.{extension}")
        ) == [media_type], extension
