# Responsiveness changes

Pipe-menu commands previously ran through `g_spawn_command_line_sync()`, stopping
Openbox's event loop until the command exited. They now run asynchronously with
nonblocking stdout collection and a disabled Loading entry. The visible menu is
rebuilt after stdout reaches EOF. Output reads are limited to 64 KiB per event-loop
dispatch and 4 MiB per command. Invalid or excessive output produces an error entry;
empty output produces an Empty menu entry. Existing command-line parsing and PATH
lookup behavior are preserved.

Clearing the menu cache, reconfiguring, or shutting down removes pending watches,
closes their pipes, and discards their results. Hiding a menu alone allows its
pending load to finish in the cache. Closing a pipe does not forcibly terminate a
script; Openbox's existing SIGCHLD handler reaps exited children. A script that
closes stdout before exiting can now display its result before it exits.

Batch client validation queues all window-attribute requests before collecting
replies when built with XCB support. It retains the event-queue synchronization,
checks for pending unmap/destroy events, and re-resolves window IDs before cleanup.
Xlib retains ownership of X events. This reduces serial request/reply waits but
still waits for the batch to finish. Without the optional `x11-xcb` and `xcb`
development packages, or with `--disable-xcb`, the original Xlib path is used.

Mouse dragging now uses `XFlush()` after a movement batch instead of `XSync()`.
The next edge-warp calculation uses the coordinates already in the motion event.
The separate synchronization calls that collect keyboard pointer-warp events
remain in place.

## Verification

The source comparison used the repository's pre-change HEAD and upstream commit
`3a2fbc65186c54855915490ec3d0b4b2ddc079ea`. Upstream has the same synchronous
pipe-menu spawn and mouse-drag synchronization; stale-client batch validation is
a Patchwork addition.

`tests/async-pipemenu.py` starts a private Xvfb display and covers:

- Escape and another keyboard action during a two-second pipe-menu delay.
- Cache replacement during an in-flight load, large output spanning multiple
  dispatches, keyboard execution, and asynchronous submenu refresh.
- Invalid, empty, and oversized output; reconfiguration during a load; repeated
  opens without descriptor growth; shutdown during a load.
- Focus cycling with 48 live clients, iconification, destruction of half the
  clients, and the temporary post-map validation timers.
- Mouse dragging, keyboard movement, and dragging across a desktop edge.

Clean builds, `make check`, the `obt/obt_unittests` binary, and the complete
Xvfb suite passed with XCB enabled and with `--disable-xcb`. `git diff --check`
also passed. The existing GLib/renderer deprecation warnings remain.

On the local Xvfb run, Escape followed by another keyboard action completed in
about 31 ms while the two-second script was still running. The pre-change binary
fails the same test's 750 ms responsiveness deadline. This is an isolated
responsiveness result, not a general desktop throughput benchmark.

## Remaining limits

Menu XML parsing, icon decoding, and rendering still run on the main thread.
Large menus can therefore still cause a pause after command output arrives.
Moving image decoding off-thread needs a separate design for decoder state,
cache ownership, and result delivery; it is not included in these changes.

Xvfb checks do not cover real GPU/compositor behavior, multi-monitor layouts,
or remote X server latency. A real X11 session test remains required before
release. These changes do not install or restart the active window manager.
