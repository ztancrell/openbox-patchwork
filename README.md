# Openbox Patchwork

> An unofficial, AI-assisted Openbox maintenance fork focused on stability,
> compatibility, and defensive hardening.

Openbox Patchwork carries a small, reviewable patch set on top of
[Openbox 3.7](https://github.com/danakj/openbox). It keeps the `openbox`
binary, configuration paths, themes, and X11 identities unchanged so existing
Openbox setups continue to work.

This is an experimental maintenance fork, not an independently audited or
upstream-supported security release. Report Patchwork bugs here, not to the
upstream Openbox maintainers.

## Patch set

- **Stale-client cleanup** detects XIDs that no longer name live windows and
  removes them from Openbox's client lists. This targets phantom Proton/Wine
  entries such as “Untitled” or “Unnamed Window” in taskbars and Alt-Tab.
- **Safe X11 text parsing** bounds property reads while preserving valid,
  length-delimited window titles that do not contain a trailing NUL byte.
- **Runtime crash guards** handle destroyed windows and invalid restored
  geometry without aborting the entire window manager.
- **Bounded image handling** rejects unreasonable image and icon dimensions
  before size calculations and allocations.
- **Session restore fixes** correct fullscreen coordinates and replace
  quadratic duplicate matching with an ownership-safe hash-table pass.
- **Responsive pipe menus** collect command output through the event loop, so
  a slow script no longer blocks window-manager input.
- **Reduced X11 waits** pipeline batch client validation when XCB is available
  and flush mouse-drag updates without waiting for server completion.
- **Additional hardening** covers theme-number parsing, fullscreen stacking,
  and GDM socket path handling.

The patch set currently tracks upstream commit
[`3a2fbc65`](https://github.com/danakj/openbox/commit/3a2fbc65186c54855915490ec3d0b4b2ddc079ea).
Upstream history and attribution remain intact in `git log` and `git blame`.

## Build and install

From a Git checkout:

```sh
./bootstrap
./configure --prefix=/usr/local --enable-debug
make -j"$(nproc)"
make check
sudo make install
```

The bundled installer performs the same workflow:

```sh
./install-openbox.sh --install-path /usr/local
```

Installation under `/usr/local` does not replace a distribution package in
`/usr/bin`. Confirm which binary is active with:

```sh
readlink -f "/proc/$(pgrep -xo openbox)/exe"
```

For Ly, include the local X session directory in `/etc/ly/config.ini`:

```ini
xsessions = /usr/share/xsessions:/usr/local/share/xsessions
```

Then select the locally installed Openbox session at login.

## Testing

Every proposed change should at minimum pass a clean build, `make check`, and
`git diff --check`. Window-lifecycle or property changes should also be tested
under Xvfb and on a real X11 session before release.

The responsiveness and window-lifecycle regression suite runs on its own Xvfb
server (requires Python 3, Xvfb, xdotool, xprop, and the Clearlooks theme):

```sh
python3 tests/async-pipemenu.py
```

XCB validation is enabled automatically when `x11-xcb` and `xcb` development
packages are available. Use `./configure --disable-xcb` to build the original
Xlib validation path. See [performance notes](PERFORMANCE.md) for behavior,
validation results, and remaining limitations.

Tests reduce risk; they do not make this fork a security audit. See
[AI_ASSISTANCE.md](AI_ASSISTANCE.md) for the project policy, review process,
and known limitations.

## Compatibility and scope

Patchwork intentionally does not rename the executable or installed Openbox
resources. The project name identifies this source distribution; applications
and desktop-session tooling still interact with Openbox normally.

Rejected experiments are not kept in the production patch set. In particular,
previous image-cache, renderer-cache, and regenerated-translation changes were
discarded after review found correctness or data-loss problems.

## Credits and license

Openbox is the work of Dana Jansens and its many contributors. See [AUTHORS](AUTHORS)
and the preserved repository history for attribution.

Openbox Patchwork is distributed under the same GNU General Public License,
version 2 or later. See [COPYING](COPYING). Copyright for existing Openbox code
remains with its original authors.

- Upstream source: <https://github.com/danakj/openbox>
- Upstream website: <http://openbox.org>
