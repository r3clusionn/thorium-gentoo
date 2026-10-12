#!/bin/bash
# Install a finished Thorium build into /opt/thorium (run as root: doas ./install.sh).
# Mirrors Chromium's Linux installer staging, minus the .deb/.rpm, desktop
# integration and the setuid chrome-sandbox (unprivileged user namespaces are
# available, so the namespace sandbox is used instead).
# NSS/NSPR/libxkbcommon come from bundle/lib (see bundle-libs.py), not Portage.
set -euo pipefail

BUILD_ROOT=${BUILD_ROOT:-$(getent passwd "${DOAS_USER:-${SUDO_USER:-$USER}}" | cut -d: -f6)/thorium-build}
OUT=$BUILD_ROOT/chromium/src/out/thorium
WRAPPER_SRC=$BUILD_ROOT/chromium/src/chrome/installer/linux/common/wrapper
BUNDLE=$BUILD_ROOT/bundle/lib
STRIP=$BUILD_ROOT/chromium/src/third_party/llvm-build/Release+Asserts/bin/llvm-strip
DEST=/opt/thorium

[[ $EUID -eq 0 ]] || { echo "run as root (doas $0)" >&2; exit 1; }
for f in thorium chrome_crashpad_handler resources.pak icudtl.dat locales/en-US.pak; do
	[[ -e $OUT/$f ]] || { echo "missing $OUT/$f - build not finished?" >&2; exit 1; }
done
[[ -e $BUNDLE/libnss3.so ]] || { echo "run bundle-libs.py first" >&2; exit 1; }

STAGE=$(mktemp -d /opt/.thorium-stage.XXXXXX)
trap 'rm -rf "$STAGE"' EXIT
chmod 755 "$STAGE"

# Binaries (stripped copies; the build tree is left untouched).
for bin in thorium chrome_crashpad_handler; do
	install -m 755 "$OUT/$bin" "$STAGE/$bin"
	"$STRIP" --strip-unneeded "$STAGE/$bin"
done

# Data files.
for f in resources.pak chrome_100_percent.pak chrome_200_percent.pak icudtl.dat \
	v8_context_snapshot.bin snapshot_blob.bin libEGL.so libGLESv2.so \
	libvk_swiftshader.so vk_swiftshader_icd.json libvulkan.so.1 product_logo_256.png thorium.svg; do
	[[ -e $OUT/$f ]] && install -m 644 "$OUT/$f" "$STAGE/$f"
done
chmod 755 "$STAGE"/*.so* 2>/dev/null || true
# English UI only (L10N="en"); Chromium falls back to en-US.
install -d -m 755 "$STAGE/locales"
install -m 644 "$OUT"/locales/en-US.pak "$OUT"/locales/en-GB.pak "$STAGE/locales/" 2>/dev/null ||
	install -m 644 "$OUT"/locales/en-US.pak "$STAGE/locales/"
for d in MEIPreload WidevineCdm; do
	[[ -d $OUT/$d ]] && cp -a "$OUT/$d" "$STAGE/$d"
done

# Bundled system libraries; the wrapper prepends $HERE/lib to LD_LIBRARY_PATH.
install -d -m 755 "$STAGE/lib"
cp -a "$BUNDLE"/. "$STAGE/lib/"
chown -R root:root "$STAGE"

# Launcher wrapper from Thorium's AVX-512 template.
sed -e 's/@@PROGNAME@@/thorium/g' -e 's/@@CHANNEL@@/stable/g' \
	-e 's/built on Ubuntu/built on Gentoo/' "$WRAPPER_SRC" > "$STAGE/thorium-browser"
chmod 755 "$STAGE/thorium-browser"

# Swap in atomically-ish, keeping the previous install as a rollback.
if [[ -d $DEST ]]; then
	rm -rf "$DEST.old"
	mv "$DEST" "$DEST.old"
fi
mv "$STAGE" "$DEST"
trap - EXIT
ln -sfn "$DEST/thorium-browser" /usr/local/bin/thorium-browser
ln -sfn "$DEST/thorium-browser" /usr/local/bin/thorium

echo "Installed to $DEST ($(du -sh "$DEST" | cut -f1)). Launch with: thorium"
[[ -d $DEST.old ]] && echo "Previous install kept at $DEST.old (delete when happy)."
exit 0
