import io
import ntpath
import os
from types import SimpleNamespace
from unittest.mock import Mock

import dronecan
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from dronecan_gui_tool import paths
from dronecan_gui_tool.widgets import file_server, node_properties


@pytest.fixture(scope='module')
def application():
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.mark.parametrize('host', [None, 'wsl.localhost', 'wsl$'])
def test_firmware_selection_through_file_service(application, monkeypatch, tmp_path, host):
    # Icons are unrelated to file access; avoid installing fonts on the test host.
    monkeypatch.setattr('qtawesome.icon', lambda *args, **kwargs: QIcon())
    payload = bytes(range(256)) * 3
    if host:
        selected = '//{}/Ubuntu-22.04/home/User/FirmwareProject/Firmware.BIN'.format(host)
        expected = selected.replace('/', '\\')
        monkeypatch.setattr(paths, 'os', SimpleNamespace(name='nt', path=ntpath))

        # Emulate a case-sensitive WSL provider: a lowercased path cannot be opened.
        def open_firmware(path, mode):
            if path != expected:
                raise FileNotFoundError(path)
            assert mode == 'rb'
            return io.BytesIO(payload)

        def getmtime(path):
            if path != expected:
                raise FileNotFoundError(path)
            return 1

        monkeypatch.setattr(node_properties, 'open', open_firmware, raising=False)
        monkeypatch.setattr(file_server, 'open', open_firmware, raising=False)
        monkeypatch.setattr(file_server.os.path, 'getmtime', getmtime)
    else:
        firmware = tmp_path / 'Firmware.BIN'
        firmware.write_bytes(payload)
        selected = str(firmware)
        expected = paths.normalize_local_path(selected)

    node = Mock(is_anonymous=False, node_id=42)
    widget = file_server.FileServerWidget(None, node)
    controls = SimpleNamespace(
        _node=node, _target_node_id=125, _file_server_widget=widget,
        window=Mock(return_value=Mock()),
    )
    monkeypatch.setattr(node_properties, 'QFileDialog', Mock(
        return_value=Mock(getOpenFileName=Mock(return_value=(selected, '')))))
    show_error = Mock()
    monkeypatch.setattr(node_properties, 'show_error', show_error)
    monkeypatch.setattr(file_server, 'flash', Mock())

    try:
        node_properties.Controls._do_firmware_update(controls)
        show_error.assert_not_called()
        node.request.assert_called_once()
        request = node.request.call_args[0][0]
        key = request.image_file_remote_path.path.decode()
        assert key == file_server.FileServer_PathKey(expected)
        assert widget._get_paths() == [expected]
        server = widget._file_server
        assert server._key_to_path[key] == expected
        assert server._resolve_path(request.image_file_remote_path) == expected

        # Adding the same selection again must not create a second lookup entry.
        widget.add_path(selected)
        assert widget._get_paths() == [expected]

        # Read all chunks using the exact short key sent in BeginFirmwareUpdate.
        received = bytearray()
        while True:
            event = SimpleNamespace(
                transfer=SimpleNamespace(source_node_id=125),
                request=dronecan.uavcan.protocol.file.Read.Request(
                    path=request.image_file_remote_path, offset=len(received)),
            )
            response = server._read(event)
            assert response.error.value == response.error.OK
            chunk = bytes(response.data)
            if not chunk:
                break
            received.extend(chunk)
            assert len(received) <= len(payload)
        assert received == payload
    finally:
        if widget._file_server:
            widget._file_server.close()
        widget._tmr.stop()
        widget.deleteLater()
