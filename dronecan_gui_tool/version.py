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

# Note: This version is incremented after the release has been made
__version_tuple__ = 1, 2, 28


# Now try to import the generated version information and override the locally managed version info

try:
    from ._version_generated import __version_tuple__
except ImportError:
    try:
        import subprocess
        git_describe = subprocess.check_output(
            ["git", "describe", "--tags", "--long", "--dirty"],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()

        is_dirty = git_describe.endswith("-dirty")
        if is_dirty:
            git_describe = git_describe[:-6] # slice off the '-dirty'

        # Split from the right, because the tag itself might contain hyphens (e.g., v1.0-beta)
        parts = git_describe.rsplit("-", 2)

        if len(parts) == 3:
            base_tag = parts[0]
            commits_since = int(parts[1])
            sha = parts[2]
            __version_tuple__ += (f"source-dev{commits_since}", sha)
            if is_dirty:
                __version_tuple__ += ("dirty", )
    except (FileNotFoundError, subprocess.CalledProcessError):
        # FileNotFoundError: The 'git' executable is not installed/available
        # CalledProcessError: The command failed (e.g., not inside a git repository)
        print("Warning: Git is not available")
        __version_tuple__ += ("source",)


