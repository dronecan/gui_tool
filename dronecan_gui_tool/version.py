#
# Copyright (C) 2016  DroneCAN Development Team  <dronecan.org>
#
# This software is distributed under the terms of the MIT License.
#
# Author: Pavel Kirienko
#         David Buzz
#         Andrew Tridgell
#
#

import re

# Note: This version is determined dynamically at build time or runtime.
__version_tuple__ = (1, 2, 28)

import os

_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_is_source = os.path.exists(os.path.join(_root_dir, 'setup.py'))

try:
    # 1. Try to get the version from setuptools_scm (live git repository state)
    from setuptools_scm import get_version
    if os.path.exists(os.path.join(_root_dir, '.git', 'shallow')):
        raise Exception("Shallow clone detected, falling back to manual version")
    _version_str = get_version(root=_root_dir, version_scheme='post-release')
    # Parse the version string into a tuple
    _parts = []
    for _part in re.split(r'[-.+]', _version_str):
        if _part:
            try:
                _parts.append(int(_part))
            except ValueError:
                _parts.append(_part)
    __version_tuple__ = tuple(_parts)
except Exception as e:
    if not _is_source:
        # 2. Try to import the generated version information (built wheels/MSIs)
        try:
            from ._version_generated import __version_tuple__  # noqa: F401
        except ImportError:
            # 3. Fall back to the manually updated version
            print("Warning: setuptools_scm is not available or failed with: ", e,
                  " and _version_generated.py not found. "
                  "Falling back to manual version.")
    else:
        print("Warning: setuptools_scm is not available or failed with: ", e,
              " and running from source. "
              "Falling back to manual version.")
