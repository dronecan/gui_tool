"""Exercise SIGINT inheritance through the GUI event loop without CAN hardware."""

import os
import signal
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.skipif(os.name == 'nt', reason='POSIX inherited SIGINT is required')
@pytest.mark.parametrize('initial_handler', ['ignored', 'ignored_replaced', 'default', 'callable'])
def test_sigint_respects_previous_handler(tmp_path, initial_handler):
    script = textwrap.dedent('''\
        import os, signal, sys
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication, QMainWindow
        mode = sys.argv[1]
        sys.argv = ['dronecan_gui_tool', '--interface', 'test']
        import dronecan_gui_tool.main as gui

        class FakeNode:
            def spin(self, _timeout): pass
            def close(self): print('node_closed', flush=True)

        class Window(QMainWindow):
            def __init__(self, *_args):
                super().__init__()
                self.poller = QTimer(self)
                self.poller.timeout.connect(lambda: None)
                self.poller.start(20)
            def show(self):
                super().show()
                QTimer.singleShot(100, lambda: os.kill(os.getpid(), signal.SIGINT))
                if mode == 'ignored_replaced':
                    QTimer.singleShot(200, lambda: signal.signal(signal.SIGINT, replacement))
                QTimer.singleShot(500, lambda: (print('alive_after_sigint', flush=True), QApplication.instance().quit()))
            def closeEvent(self, event):
                print('window_closed', flush=True)
                super().closeEvent(event)

        gui.dronecan.make_node = lambda *_args, **_kwargs: FakeNode()
        gui.MainWindow = Window
        if mode == 'callable':
            signal.signal(signal.SIGINT, lambda *_args: None)
        elif mode == 'default':
            signal.signal(signal.SIGINT, signal.default_int_handler)
        def replacement(*_args):
            pass
        previous = signal.getsignal(signal.SIGINT)
        print('previous_ignored', previous is signal.SIG_IGN, flush=True)
        try:
            gui.main()
        except SystemExit as exc:
            print('exit_code', exc.code, flush=True)
        print('restored', signal.getsignal(signal.SIGINT) is previous, flush=True)
        print('replacement_retained', signal.getsignal(signal.SIGINT) is replacement, flush=True)
    ''')
    env = os.environ.copy()
    env.update({'QT_QPA_PLATFORM': 'offscreen', 'HOME': str(tmp_path), 'XDG_CONFIG_HOME': str(tmp_path)})

    def ignore_sigint():
        signal.signal(signal.SIGINT, signal.SIG_IGN)

    completed = subprocess.run(
        [sys.executable, '-u', '-c', script, initial_handler],
        env=env,
        preexec_fn=ignore_sigint if initial_handler in ('ignored', 'ignored_replaced') else None,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert 'node_closed' in completed.stdout
    assert 'exit_code 0' in completed.stdout
    if initial_handler == 'ignored_replaced':
        assert 'replacement_retained True' in completed.stdout
    else:
        assert 'restored True' in completed.stdout
    if initial_handler in ('ignored', 'ignored_replaced'):
        assert 'previous_ignored True' in completed.stdout
        assert 'alive_after_sigint' in completed.stdout
    else:
        assert 'previous_ignored False' in completed.stdout
        assert 'window_closed' in completed.stdout
        assert 'alive_after_sigint' not in completed.stdout
