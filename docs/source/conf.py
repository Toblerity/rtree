# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import sys

sys.path.append("../../")

import rtree  # noqa: E402

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Rtree"
copyright = "2019, Sean Gilles, Howard Butler, and contributors"
author = "Sean Gilles, Howard Butler, and contributors"
version = release = rtree.__version__

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx.ext.ifconfig",
    "sphinx_issues",
]

templates_path = ["_templates"]
exclude_patterns = []

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output


html_theme = "nature"
htmlhelp_basename = "Rtreedoc"

# -- Options for LaTeX output --------------------------------------------

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [("index", "Rtree.tex", "Rtree Documentation", author, "manual")]

pdf_documents = [("index", "Rtree", "Rtree Documentation", "The Rtree Team")]

pdf_language = "en_US"
pdf_fit_mode = "overflow"

# -- Extension configuration -------------------------------------------------

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

# sphinx.ext.autodoc
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"

# sphinx-issues
issues_github_path = "Toblerity/rtree"
issues_commit_prefix = ""
