"""Sphinx configuration for the Contacts API documentation."""

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

# autodoc imports the application modules, and the settings require these
# variables. Real values from the environment are kept; placeholders are used
# only so the documentation can be built without a .env file.
for name, value in {
    "POSTGRES_USER": "docs",
    "POSTGRES_PASSWORD": "docs",
    "POSTGRES_DB": "docs",
    "JWT_SECRET": "docs",
    "MAIL_FROM": "docs@example.com",
    "MAIL_SERVER": "localhost",
    "CLOUDINARY_NAME": "docs",
    "CLOUDINARY_API_KEY": "docs",
    "CLOUDINARY_API_SECRET": "docs",
}.items():
    os.environ.setdefault(name, value)

project = "Contacts API"
copyright = "2026, Volodymyr"
author = "Volodymyr"
release = "0.3.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
autodoc_member_order = "bysource"
napoleon_google_docstring = True

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
