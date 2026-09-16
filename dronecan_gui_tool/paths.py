import os


def normalize_local_path(path):
    """Return an absolute local path, preserving case on WSL shares.

    Windows normcase() lowercases paths, but files accessed through either
    WSL UNC namespace belong to a case-sensitive Linux filesystem.
    """
    path = os.path.abspath(os.path.expanduser(path))
    if os.name == 'nt' and path.lower().startswith(('\\\\wsl.localhost\\', '\\\\wsl$\\')):
        return path
    return os.path.normcase(path)
