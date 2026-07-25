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

import os
import subprocess
import re

# Note: This version is determined dynamically at build time or runtime.
__version_tuple__ = None

# 1. Try running git describe first (live git repository state)
try:

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
        
        # Parse base tag into tuple (e.g., "1.2.28" -> (1, 2, 28))
        # Remove leading 'v' if present
        if base_tag.startswith('v'):
            base_tag = base_tag[1:]
        
        tag_parts = tuple(int(x) for x in base_tag.split('.') if x.isdigit())
        
        __version_tuple__ = tag_parts
        if commits_since > 0:
            __version_tuple__ += (f"source-post{commits_since}", sha)
        if is_dirty:
            __version_tuple__ += ("dirty", )
except (FileNotFoundError, subprocess.CalledProcessError):
    # 2. Try to import the generated version information (built wheels/MSIs)
    try:
        from ._version_generated import __version_tuple__
    except ImportError:
        # 3. Fall back to reading .git_archival.txt (GitHub source ZIPs)
        __version_tuple__ = (0, 0, 0, "unknown")
        
        archival_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".git_archival.txt")
        if os.path.isfile(archival_path):
            with open(archival_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract node hash
            node_match = re.search(r'^node:[ \t]*([a-f0-9]{40})$', content, re.MULTILINE)
            # Extract describe-name
            describe_match = re.search(r'^describe-name:[ \t]*(.+)$', content, re.MULTILINE)
            # Extract ref-names
            ref_match = re.search(r'^ref-names:[ \t]*(.+)$', content, re.MULTILINE)
            
            if node_match and not node_match.group(1).startswith('$'):
                sha = 'g' + node_match.group(1)[:7]
                base_tag = None
                commits_since = 0

                if describe_match and not describe_match.group(1).startswith('$'):
                    describe_str = describe_match.group(1).strip()
                    parts = describe_str.rsplit("-", 2)

                    if len(parts) == 3 and parts[1].isdigit() and parts[2].startswith('g'):
                        base_tag = parts[0]
                        commits_since = int(parts[1])
                    else:
                        base_tag = describe_str

                if not base_tag and ref_match and not ref_match.group(1).startswith('$'):
                    refs = ref_match.group(1).split(', ')
                    tags = [r[5:] for r in refs if r.startswith('tag: ')]
                    if tags:
                        base_tag = tags[0]
                        
                if base_tag:
                    if base_tag.startswith('v'):
                        base_tag = base_tag[1:]
                        
                    tag_parts = tuple(int(x) for x in base_tag.split('.') if x.isdigit())
                    if tag_parts:
                        __version_tuple__ = tag_parts
                        if commits_since > 0:
                            __version_tuple__ += (f"source-post{commits_since}", sha)
                    else:
                        __version_tuple__ = (0, 0, 0, "source", sha)
                else:
                    __version_tuple__ = (0, 0, 0, "source", sha)
        else:
            print("Warning: Git is not available and .git_archival.txt not found")
