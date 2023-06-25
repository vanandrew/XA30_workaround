#!/usr/bin/env python3
import os
import sys
import site
import setuptools

# get the project directory
PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))

# get scripts path
SCRIPTSPATH = os.path.join(PROJECT_DIR, "xa30_workaround", "scripts")


if __name__ == "__main__":
    # setup entry points scripts
    entry_points = {
        "console_scripts": [
            "{0}=xa30_workaround.scripts.{0}:main".format(f.split(".")[0])
            for f in os.listdir(SCRIPTSPATH)
            if not ("__pycache__" in f or "__init__.py" in f or "common" in f or ".DS_Store" in f)
        ]
    }

    # create setup options
    setup_options = {"entry_points": entry_points}

    # run setup
    setuptools.setup(**setup_options)
