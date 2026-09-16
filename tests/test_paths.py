import ntpath
import posixpath
from types import SimpleNamespace

import pytest

from dronecan_gui_tool import paths


@pytest.fixture
def windows_paths(monkeypatch):
    # Exercise Windows semantics on every CI host without changing global os.path.
    monkeypatch.setattr(paths, 'os', SimpleNamespace(name='nt', path=ntpath))


@pytest.mark.parametrize('host', ['wsl.localhost', 'wsl$', 'WSL.LOCALHOST', 'WSL$'])
@pytest.mark.parametrize('separator', ['\\', '/'])
def test_wsl_preserves_case(windows_paths, host, separator):
    expected = '\\\\' + host + '\\Ubuntu-22.04\\home\\User\\FirmwareProject\\Firmware.BIN'
    selected = expected.replace('\\', separator)
    normalized = paths.normalize_local_path(selected)
    assert normalized == expected
    assert paths.normalize_local_path(normalized) == normalized


@pytest.mark.parametrize('selected', [
    r'C:\Users\User\Firmware.BIN',
    'C:/Users/User/Build/../Firmware.BIN',
    r'Build\Firmware.BIN',
    r'~\Firmware.BIN',
    r'\\Server\Share\Firmware.BIN',
    '//Server/Share/Build/../Firmware.BIN',
    r'\\wsl.localhost.example\Share\Firmware.BIN',
    r'\\wsl$backup\Share\Firmware.BIN',
])
def test_other_windows_paths_keep_existing_behavior(windows_paths, monkeypatch, selected):
    monkeypatch.setenv('USERPROFILE', r'C:\Users\User')
    expected = ntpath.normcase(ntpath.abspath(ntpath.expanduser(selected)))
    assert paths.normalize_local_path(selected) == expected


@pytest.mark.parametrize('selected', [
    '/home/User/FirmwareProject/Firmware.BIN',
    'Build/../Firmware.BIN',
    '~/Firmware.BIN',
    '//wsl.localhost/Ubuntu-22.04/home/User/Firmware.BIN',
])
def test_posix_paths_keep_existing_behavior(monkeypatch, selected):
    monkeypatch.setattr(paths, 'os', SimpleNamespace(name='posix', path=posixpath))
    monkeypatch.setenv('HOME', '/home/User')
    expected = posixpath.abspath(posixpath.expanduser(selected))
    assert paths.normalize_local_path(selected) == expected
