#!/usr/bin/env python3
"""Exercise pipe-menu responsiveness/lifetime under a private Xvfb server.

Run after building: python3 tests/async-pipemenu.py [path/to/openbox]
Requires Xvfb, xdotool and xprop. Never connects to the user's desktop.
"""
import ctypes
import os
import re
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time
from xml.sax.saxutils import escape


def wait_for(predicate, message, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError(message)


def main():
    binary = Path(sys.argv[1] if len(sys.argv) > 1 else 'openbox/openbox').resolve()
    with tempfile.TemporaryDirectory(prefix='openbox-pipe-test-') as tmp:
        tmp = Path(tmp)
        processes = []
        logs = (tmp / 'xvfb.log', tmp / 'wm.log')
        try:
            with logs[0].open('w') as log:
                read_fd, write_fd = os.pipe()
                xvfb = subprocess.Popen(
                    ['Xvfb', '-displayfd', str(write_fd), '-screen', '0',
                     '1024x768x24', '-nolisten', 'tcp'], pass_fds=(write_fd,),
                    stdout=log, stderr=log)
                processes.append(xvfb)
                os.close(write_fd)
                try:
                    assert select.select([read_fd], [], [], 5)[0], 'Xvfb startup timeout'
                    display = os.read(read_fd, 32).decode().strip()
                    assert display, 'Xvfb could not open its socket'
                finally:
                    os.close(read_fd)
            env = dict(os.environ, DISPLAY=':' + display,
                       XDG_CONFIG_HOME=str(tmp), LC_ALL='C')

            def run(*args):
                return subprocess.check_output(args, env=env, text=True,
                                               stderr=subprocess.DEVNULL, timeout=5).strip()

            def key(keys):
                run('xdotool', 'key', '--clearmodifiers', keys)

            script = tmp / 'pipe.py'
            script.write_text('''import pathlib, sys, time
p = pathlib.Path(sys.argv[1])
mode = (p / 'mode').read_text()
(p / 'started').touch()
if mode == 'slow':
    time.sleep(2)
if mode == 'invalid':
    print('not xml')
elif mode == 'empty':
    print('<openbox_pipe_menu/>')
elif mode == 'oversized':
    try:
        print('x' * (5 * 1024 * 1024))
    except BrokenPipeError:
        pass
else:
    padding = '<!--' + 'x' * 180000 + '-->' if mode == 'large' else ''
    print('<openbox_pipe_menu>' + padding + '<item label="Ready"><action name="Execute"><command>touch ' + str(p / 'executed') + '</command></action></item></openbox_pipe_menu>')
(p / 'finished').touch()
''')
            command = escape(f'{sys.executable} {script} {tmp}')
            menu = tmp / 'menu.xml'
            menu.write_text(f'''<openbox_menu>
<menu id="pipe" label="Pipe" execute="{command}"/>
<menu id="root" label="Root"><menu id="pipe"/></menu>
</openbox_menu>''')
            rc = tmp / 'rc.xml'
            rc.write_text(f'''<openbox_config>
<theme><name>Clearlooks</name></theme>
<desktops><number>2</number></desktops>
<keyboard>
<keybind key="A-Tab"><action name="NextWindow"/></keybind>
<keybind key="F8"><action name="Move"/></keybind>
<keybind key="F12"><action name="ShowMenu"><menu>pipe</menu></action></keybind>
<keybind key="F11"><action name="ShowMenu"><menu>root</menu></action></keybind>
<keybind key="F9"><action name="Execute"><command>touch {tmp / 'responsive'}</command></action></keybind>
</keyboard>
<mouse><dragThreshold>1</dragThreshold><screenEdgeWarpTime>100</screenEdgeWarpTime>
<context name="Frame">
<mousebind button="A-Left" action="Drag"><action name="Move"/></mousebind>
</context></mouse>
<menu><file>{menu}</file><submenuShowDelay>0</submenuShowDelay></menu>
</openbox_config>''')
            (tmp / 'mode').write_text('slow')
            with logs[1].open('w') as log:
                wm = subprocess.Popen([str(binary), '--sm-disable', '--config-file', str(rc)],
                                      env=env, stdout=log, stderr=log, start_new_session=True)
                processes.append(wm)
            wait_for(lambda: 'window id' in run('xprop', '-root', '_NET_SUPPORTING_WM_CHECK'),
                     'WM startup failed')

            def open_menu(mode, nested=False):
                for name in ('started', 'finished', 'executed'):
                    (tmp / name).unlink(missing_ok=True)
                (tmp / 'mode').write_text(mode)
                key('F11' if nested else 'F12')
                if nested:
                    key('Down')
                    key('Right')
                wait_for(lambda: (tmp / 'started').exists(), 'pipe did not start')

            open_menu('slow')
            start = time.monotonic()
            key('Escape')
            key('F9')
            wait_for(lambda: (tmp / 'responsive').exists(),
                     'WM blocked on pipe output', timeout=0.75)
            elapsed = time.monotonic() - start
            assert not (tmp / 'finished').exists(), 'pipe ended before responsiveness check'
            print(f'PASS: Escape and another action while pipe sleeps: {elapsed:.3f}s')

            # Clear the old generation while it is still running, then execute
            # the new generation's output. The old callback must never return.
            open_menu('large')
            wait_for(lambda: (tmp / 'finished').exists(), 'large output did not finish')
            time.sleep(0.15)
            key('Return')
            wait_for(lambda: (tmp / 'executed').exists(), 'loaded menu action failed')
            print('PASS: cache replacement, output over one dispatch, keyboard execution')
            time.sleep(2.1)

            open_menu('normal', nested=True)
            wait_for(lambda: (tmp / 'finished').exists(), 'submenu did not finish')
            time.sleep(0.15)
            key('Return')
            wait_for(lambda: (tmp / 'executed').exists(), 'nested pipe action failed')
            print('PASS: asynchronous submenu refresh and execution')

            for mode in ('invalid', 'empty', 'oversized'):
                open_menu(mode)
                wait_for(lambda: (tmp / 'finished').exists(), mode + ' did not finish')
                time.sleep(0.15)
                key('Escape')
                assert wm.poll() is None, mode + ' killed WM'
            print('PASS: malformed, empty and oversized output')

            open_menu('slow')
            os.kill(wm.pid, signal.SIGUSR2)
            time.sleep(2.3)
            assert wm.poll() is None, 'reconfigure with pending output killed WM'
            open_menu('normal')
            wait_for(lambda: (tmp / 'finished').exists(), 'post-reconfigure pipe failed')
            time.sleep(0.15)
            key('Return')
            wait_for(lambda: (tmp / 'executed').exists(), 'post-reconfigure action failed')
            print('PASS: reconfigure while pipe is pending')

            before = len(list(Path(f'/proc/{wm.pid}/fd').iterdir()))
            for _ in range(8):
                open_menu('normal')
                wait_for(lambda: (tmp / 'finished').exists(), 'repeated pipe failed')
                time.sleep(0.08)
                key('Escape')
            after = len(list(Path(f'/proc/{wm.pid}/fd').iterdir()))
            assert after <= before, f'file descriptor leak: {before} -> {after}'
            print('PASS: repeated opens do not leak descriptors')

            # Keep real client windows alive while exercising focus validation,
            # destruction, iconification and both movement paths.
            xlib = ctypes.CDLL('libX11.so.6')
            pointer, window = ctypes.c_void_p, ctypes.c_ulong
            xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
            xlib.XOpenDisplay.restype = pointer
            xlib.XDefaultRootWindow.argtypes = [pointer]
            xlib.XDefaultRootWindow.restype = window
            xlib.XCreateSimpleWindow.argtypes = [pointer, window, ctypes.c_int,
                ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
                ctypes.c_ulong, ctypes.c_ulong]
            xlib.XCreateSimpleWindow.restype = window
            for name in ('XMapWindow', 'XDestroyWindow'):
                getattr(xlib, name).argtypes = [pointer, window]
            xlib.XFlush.argtypes = [pointer]
            xlib.XCloseDisplay.argtypes = [pointer]
            # Malformed-output diagnostics can create Openbox prompt windows.
            existing_clients = {int(x, 16) for x in re.findall(
                r'0x[0-9a-fA-F]+', run('xprop', '-root', '_NET_CLIENT_LIST'))}
            connection = xlib.XOpenDisplay(env['DISPLAY'].encode())
            assert connection, 'client connection failed'
            try:
                root = xlib.XDefaultRootWindow(connection)
                windows = [xlib.XCreateSimpleWindow(connection, root, 100, 100,
                                                    180, 100, 0, 0, 0)
                           for _ in range(48)]
                for wid in windows:
                    xlib.XMapWindow(connection, wid)
                xlib.XFlush(connection)

                def clients():
                    return {int(x, 16) for x in re.findall(
                        r'0x[0-9a-fA-F]+', run('xprop', '-root', '_NET_CLIENT_LIST'))} - existing_clients

                try:
                    wait_for(lambda: clients() == set(windows), 'clients not managed')
                except AssertionError:
                    print('Expected:', windows, 'Actual:', clients(), file=sys.stderr)
                    print(run('xprop', '-root', '_NET_CLIENT_LIST'), file=sys.stderr)
                    raise
                run('xdotool', 'windowminimize', str(windows[-1]))
                for _ in range(3):
                    key('alt+Tab')
                assert clients() == set(windows), 'validation removed a live client'
                for wid in windows[:24]:
                    xlib.XDestroyWindow(connection, wid)
                xlib.XFlush(connection)
                for _ in range(3):
                    key('alt+Tab')
                wait_for(lambda: clients() == set(windows[24:]), 'destroyed clients remain')
                print('PASS: focus cycling with 48 clients, iconification and destruction')

                target = str(windows[24])
                run('xdotool', 'windowactivate', '--sync', target)
                run('xdotool', 'windowmove', '--sync', target, '200', '200')

                def geometry():
                    return {k: int(v) for k, v in (line.split('=') for line in
                        run('xdotool', 'getwindowgeometry', '--shell', target).splitlines())}

                before = geometry()
                run('xdotool', 'mousemove', '--window', target, '30', '30',
                    'keydown', 'Alt_L', 'mousedown', '1',
                    'mousemove_relative', '--', '10', '0')
                time.sleep(0.05)
                run('xdotool', 'mousemove_relative', '--', '60', '45')
                time.sleep(0.05)
                run('xdotool', 'mouseup', '1', 'keyup', 'Alt_L')
                after = geometry()
                assert after['X'] > before['X'] + 20 and after['Y'] > before['Y'] + 20, \
                    ('drag did not move window', before, after)
                key('F8')
                key('Right')
                key('Return')
                assert geometry()['X'] > after['X'], 'keyboard move failed'
                print('PASS: mouse dragging and keyboard pointer-warp movement')

                run('xdotool', 'mousemove', '--window', target, '30', '30',
                    'keydown', 'Alt_L', 'mousedown', '1',
                    'mousemove_relative', '--', '10', '0')
                time.sleep(0.05)
                run('xdotool', 'mousemove', '1023', '350')
                wait_for(lambda: run('xdotool', 'get_desktop') == '1',
                         'dragging to desktop edge did not switch desktop', timeout=2)
                run('xdotool', 'mouseup', '1', 'keyup', 'Alt_L')
                # Allow all post-map validation rounds to run as well.
                time.sleep(5.1)
                assert clients() == set(windows[24:]), 'timer removed a live client'
                print('PASS: drag across desktop edge and post-map validation timers')
            finally:
                xlib.XCloseDisplay(connection)

            open_menu('slow')
            wm.terminate()
            wm.wait(timeout=1)
            print('PASS: shutdown does not wait for pipe completion')
        except Exception:
            for path in logs:
                if path.exists():
                    print(path.name + ':\n' + path.read_text()[-6000:], file=sys.stderr)
            raise
        finally:
            # The WM owns a private process group, including any pending menu
            # scripts. Do not leave those scripts behind after a failing test.
            if len(processes) > 1:
                try:
                    os.killpg(processes[1].pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)


if __name__ == '__main__':
    main()
