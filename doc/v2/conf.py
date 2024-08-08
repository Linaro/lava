# Copyright (C) 2016-present Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from os.path import abspath
from sys import path

import sphinx_bootstrap_theme

path.insert(0, abspath("../.."))

from lava_common.version import version as lava_version

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

project = "LAVA"
copyright = "2010-2024, Linaro Limited"
version = lava_version()
release = version

# List of directories, relative to source directory, that shouldn't be searched
# for source files.
exclude_patterns = ["pages/reference-architecture"]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  Major themes that come with
# Sphinx are currently 'default' and 'sphinxdoc'.
html_theme = "bootstrap"
html_theme_path = sphinx_bootstrap_theme.get_html_theme_path()

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    "navbar_sidebarrel": True,
    "navbar_links": [("Index", "genindex"), ("Contents", "contents")],
}

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
html_logo = "images/lava.png"

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
html_favicon = "./favicon.ico"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# If true, links to the reST sources are added to the pages.
html_show_sourcelink = False

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
html_show_sphinx = True

# Output file base name for HTML help builder.
htmlhelp_basename = "LAVADocumentation"
