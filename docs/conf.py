"""Configuração do Sphinx para a documentação do projeto."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import django

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

project = "SME-Abrangencia-Microsservico"
author = "SME"
release = "0.1.0"
language = "pt_BR"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.graphviz",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

autosectionlabel_prefix_document = True

myst_enable_extensions = [
    "colon_fence",
    "deflist",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

root_doc = "index"
templates_path = ["_templates"]
exclude_patterns = ["_build", "_cov", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_title = "SME-Abrangencia-Microsservico"
html_short_title = "Abrangência Docs"
html_static_path = ["_static"]

graphviz_output_format = "png"

autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_default_options = {
    "undoc-members": False,
    "show-inheritance": True,
}

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_use_param = False
napoleon_use_rtype = False
