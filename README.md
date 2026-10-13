# thorium-gentoo

The scripts that build and install the Thorium browser from source for one Gentoo laptop, without adding packages to the system. Thorium is a Chromium fork tuned with compiler optimizations; this build adds AVX-512 and drops CUPS. NSS, NSPR and libxkbcommon are bundled from Gentoo's official binary packages instead of installed system-wide, the way firefox-bin carries its own NSS. The result installs to `/opt/thorium` and is the laptop's only browser.

**Status:** in daily use on the target laptop (HP OmniBook 7, Ryzen AI 9 HX 475): Thorium 156.0.8078.28. The build tree has since been deleted to free space; a rebuild starts from Thorium's sources again.

![Terminal output on a dark background: "thorium-browser --version" prints "Thorium 156.0.8078.28 stable, built on Gentoo (AVX-512)"; BUNDLED_VERSIONS lists dev-libs/nspr-4.39, dev-libs/nss-3.125 and x11-libs/libxkbcommon-1.13.2; ldd with system libraries only finds 5 libraries missing, and with /opt/thorium/lib none; du -sh /opt/thorium prints 376M](docs/images/version.png)

## Features

- **`args.gn.local`:** Thorium's own release arguments (AVX-512 profile `avx512_skx`, ThinLTO, PGO, CFI, proprietary codecs, VA-API, Widevine) plus `use_cups = false`, since CUPS isn't installed.
- **`bundle-libs.py`:** downloads NSS, NSPR and libxkbcommon from Gentoo's x86-64-v3 binhost, checks each package's SHA-1 against the binhost index, and keeps only the shared libraries.
- **`install.sh`:** stages a stripped copy of the build into `/opt/thorium` with the bundled libraries and Thorium's AVX-512 launcher, then swaps it in atomically, keeping the previous install as `/opt/thorium.old`. English locales only. No setuid sandbox helper: the namespace sandbox is used.
- **`policies.json`:** the managed policies installed to `/etc/chromium/policies/managed/thorium.json`: no background mode, no network prediction, memory saver on, and the on-device model download off.
- **`env.sh`:** the paths and depot_tools setup the build uses.

## How to install

Requires about 100 GB of free disk space, Python 3, git, and a CPU with AVX-512 (or change `thorium_x86_profile` in `args.gn.local`).

1. Fetch and build Thorium following its own instructions, with the paths from this repo:

   ```sh
   . ./env.sh                         # THOR_DIR, CR_DIR, depot_tools on PATH
   # check out Chromium and Thorium as Thorium's README describes, then:
   cp args.gn.local "$CR_DIR/out/thorium/args.gn"
   autoninja -C "$CR_DIR/out/thorium" thorium_all
   ```

2. Bundle the libraries and install:

   ```sh
   python3 bundle-libs.py             # -> ~/thorium-build/bundle/lib
   doas ./install.sh                  # -> /opt/thorium, /usr/local/bin/thorium
   doas install -Dm644 policies.json /etc/chromium/policies/managed/thorium.json
   ```

Rerun `bundle-libs.py` with every rebuild to pick up security updates to NSS.

## How to use

```sh
thorium
```

On a 2x display, a wrapper that fixes GTK's file dialog size is useful (it otherwise applies the scale twice):

```sh
#!/bin/sh
export GDK_SCALE=2 GDK_DPI_SCALE=0.5
exec /opt/thorium/thorium-browser --force-device-scale-factor=2 --use-angle=gl-egl "$@"
```

`--use-angle=gl-egl` runs ANGLE over EGL instead of GLX. With X at depth 30 (10 bits per channel), the GLX path can't bind Chromium's 8-bit video frames and page buffers, because the screen has no depth-24 visuals, and videos play as a white rectangle.

## How it works

- **Libraries:** Chromium's launcher prepends `/opt/thorium/lib` to `LD_LIBRARY_PATH`, so the bundled NSS, NSPR and libxkbcommon are found there. glibc, GTK and the X libraries come from the system. The softokn module still uses the system's sqlite and zlib.
- **Choosing packages:** `bundle-libs.py` reads the binhost's `Packages` index, takes the newest version of each package, and skips the Wayland-enabled libxkbcommon build. It extracts only matching `lib64/*.so*` files from the gpkg's inner image and refuses symlinks that point outside the directory.
- **Install:** binaries are stripped with Chromium's own llvm-strip. Data files, Widevine and MEIPreload are copied. The tree is owned by root and moved into place in one rename.

## Measurements

| | |
|---|---|
| Installed size | 376 MB (`/opt/thorium`) |
| Libraries missing from the system | 5 (nspr4, nss3, nssutil3, smime3, xkbcommon), all bundled |
| System packages added | 0 |

## Verification

- `ldd` with the bundled libraries reports no missing libraries; without them it reports exactly the 5 bundled ones.
- `thorium-browser --version` reports the AVX-512 Gentoo build, and the browser is in daily use (Alt+W in dwm).
- The bundle's versions are recorded in `/opt/thorium/lib/BUNDLED_VERSIONS`.

## Limits

- Made for one machine: AVX-512 (Zen 5), X11, PipeWire, no CUPS. Printing isn't available.
- The bundled libraries only update when `bundle-libs.py` and `install.sh` are rerun.
- The checkout and build steps themselves follow Thorium's documentation and aren't scripted here.

## License

BSD-3-Clause, as Chromium and Thorium (see `LICENSE`).
