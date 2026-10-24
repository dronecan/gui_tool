import io
import ntpath
from types import SimpleNamespace
from unittest.mock import Mock

import dronecan
import pytest

from dronecan_gui_tool import paths
from dronecan_gui_tool.widgets import node_properties


def make_param(name, integer_value):
    value = dronecan.uavcan.protocol.param.Value(integer_value=integer_value)
    return SimpleNamespace(name=name, value=value)


def make_config_params(monkeypatch, selected, params):
    monkeypatch.setattr(node_properties, 'QFileDialog', Mock(return_value=Mock(
        getSaveFileName=Mock(return_value=(selected, '')),
        getOpenFileName=Mock(return_value=(selected, '')))))
    config = SimpleNamespace(_params=params, save_param=Mock())
    config.param_as_string = lambda *args: node_properties.ConfigParams.param_as_string(config, *args)
    return config


@pytest.mark.parametrize('host', ['wsl.localhost', 'wsl$'])
def test_param_files_preserve_case_on_wsl_shares(monkeypatch, host):
    selected = '//{}/Ubuntu-22.04/home/User/Params/Node.PARM'.format(host)
    expected = selected.replace('/', '\\')
    monkeypatch.setattr(paths, 'os', SimpleNamespace(name='nt', path=ntpath))

    # Emulate a case-sensitive WSL provider: a lowercased path cannot be opened.
    files = {}

    class ParamFile(io.StringIO):
        def __init__(self, path, mode):
            if path != expected:
                raise FileNotFoundError(path)
            super().__init__(files.get(path, '') if mode == 'r' else '')
            self._path, self._mode = path, mode

        def close(self):
            if self._mode == 'w':
                files[self._path] = self.getvalue()
            super().close()

    monkeypatch.setattr(node_properties, 'open', ParamFile, raising=False)

    params = [make_param('PARAM_A', 1), make_param('PARAM_B', 2)]
    config = make_config_params(monkeypatch, selected, params)
    node_properties.ConfigParams._do_save_to_file(config)
    assert files[expected] == 'PARAM_A 1\nPARAM_B 2\n'

    files[expected] = 'PARAM_A 1\nPARAM_B 5\n'
    node_properties.ConfigParams._do_load_from_file(config)
    config.save_param.assert_called_once_with('PARAM_B', params[1].value, '5')
