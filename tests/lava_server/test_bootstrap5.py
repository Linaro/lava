# Copyright (C) 2026 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Static guard against Bootstrap 3 leftovers (bootstrap v5 migration).

Greps the template/JS/py tree for BS3-only tokens and jQuery plugin
invocations that no longer exist in Bootstrap 5. Vendored files are excluded
by name, not by directory: every static dir is named ``js/``, so a directory
exclusion would blind the runtime-break pattern to query.js, chart.js and
bootbox.data.toggle.js, the files it must watch.
"""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

APPS = ["lava_server", "lava_results_app", "lava_scheduler_app"]

# BS3-only tokens + jQuery plugin calls removed in Bootstrap 5.
PATTERNS = [
    "data-toggle=",
    "data-target=",
    'class="pager',
    "glyphicon",
    "btn-default",
    "form-inline",
    # class-attribute context, so the icon class bi-text-left does not match
    "[\"' >]text-(right|left)[ \"']",
    "badge-(primary|secondary|success|info|warning|danger)",
    'class="close\\b',
    "font-weight-|font-italic|text-monospace",
    "pull-left",
    "pull-right",
    "input-group-addon",
    "panel-heading",
    "panel-body",
    r"col-xs-\d",
    "label-info|label-danger|label-primary",
    "dropdown-menu-right",
    "control-label",
    "help-block",
    "img-responsive",
    # BS3 tab markup: <li role="presentation">; BS5 uses .nav-item/.nav-link
    'role="presentation"',
    # runtime-break pattern: jQuery plugin API (gone from BS5 core)
    r"\$\([^)]*\)\.(modal|collapse|tab|tooltip|popover|dropdown)\(",
]

# Vendored assets are excluded by filename, not by directory (see docstring).
VENDORED_EXCLUDES = [
    "--exclude=bootstrap-5.3.8.js",
    "--exclude=bootbox.js",
    "--exclude=jquery*",
    "--exclude=popper*",
]


def test_no_bootstrap3_leftovers():
    offenders = []
    for pattern in PATTERNS:
        result = subprocess.run(
            [
                "grep",
                "-rn",
                "-E",
                "--include=*.html",
                "--include=*.js",
                "--include=*.py",
                *VENDORED_EXCLUDES,
                "-e",
                pattern,
                "--",
                *APPS,
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            # grep exits 1 on "no match", the expected case here
            check=False,
        )
        if result.returncode == 0:
            offenders.append(f"pattern {pattern!r}:\n{result.stdout}")
    assert not offenders, "Bootstrap 3 leftovers found:\n" + "\n".join(offenders)
