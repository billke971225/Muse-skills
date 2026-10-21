#!/bin/bash
# Cockpit Tools launcher — persistent home-dir install (.deb extracted, no system install).
# - Display: prefer remote-browser stack :99 (visible via noVNC); else private Xvfb :98
# - Mesa/EGL libs from ./syslibs (system libegl1 is wiped on VM rebuilds)
# - WebKitGTK 4.1 + deps extracted into ./sysroot (AppImage-bundled WebKit renders blank here)
# - WebKit fixes: software GL + no dmabuf + no compositing
export HOME=/home/hatch
BASE=/home/hatch/workspace/cockpit-tools
# Under systemd, wait briefly for the remote-browser desktop (:99) so the window
# lands where the user can see it; fall back to a private :98 after ~2 minutes.
if [ -n "$COCKPIT_WAIT_DISPLAY" ]; then
  for i in $(seq 1 24); do [ -e /tmp/.X11-unix/X99 ] && break; sleep 5; done
fi
if [ -e /tmp/.X11-unix/X99 ]; then
  export DISPLAY=:99
  AUTH=$(python3 -c "
import os
for pid in os.listdir('/proc'):
    if not pid.isdigit(): continue
    try:
        argv=[a.decode(errors='ignore') for a in open(f'/proc/{pid}/cmdline','rb').read().split(b'\0') if a]
        if argv and 'Xvfb' in argv[0] and ':99' in argv and '-auth' in argv:
            print(argv[argv.index('-auth')+1]); break
    except Exception: pass
" 2>/dev/null)
  [ -n "$AUTH" ] && export XAUTHORITY="$AUTH"
else
  export DISPLAY=:98
fi
export LIBGL_ALWAYS_SOFTWARE=1
# Do NOT disable the DMABUF renderer: WebKitGTK 2.52 only paints through it here.
# No /dev/dri in this VM, so force the shared-memory transport instead of GBM.
export WEBKIT_DMABUF_RENDERER_DISABLE_GBM=1
export WEBKIT_DMABUF_RENDERER_FORCE_SHM=1
# No compositor on Xvfb -> no vblank events; force the timer fallback or frames never present.
export WEBKIT_FORCE_VBLANK_TIMER=1
export WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1
export EGL_PLATFORM=x11
# Mesa in syslibs is invisible to glvnd without its vendor JSON, and its DRI drivers
# live in the sysroot: without both, EGL display creation fails (EGL_BAD_PARAMETER).
export __EGL_VENDOR_LIBRARY_DIRS=/home/hatch/workspace/blender/syslibs/usr/share/glvnd/egl_vendor.d
SYSROOT_LIBS="$BASE/sysroot/usr/lib/x86_64-linux-gnu"
export LIBGL_DRIVERS_PATH="$SYSROOT_LIBS/dri"
export LD_LIBRARY_PATH="$SYSROOT_LIBS:$BASE/syslibs:$BASE/deb-root/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export WEBKIT_EXEC_PATH="$SYSROOT_LIBS/webkit2gtk-4.1"
export WEBKIT_INJECTED_BUNDLE_PATH="$SYSROOT_LIBS/webkit2gtk-4.1/injected-bundle"
export GST_PLUGIN_PATH="$SYSROOT_LIBS/gstreamer-1.0"
export XDG_DATA_DIRS="$BASE/sysroot/usr/share:$BASE/deb-root/usr/share${XDG_DATA_DIRS:+:$XDG_DATA_DIRS}"
# WebKitGTK looks up helper processes at the compiled-in /usr path (WEBKIT_EXEC_PATH
# is ignored by this build); /usr is wiped on VM rebuilds, so recreate the symlink.
ln -sfn "$SYSROOT_LIBS/webkit2gtk-4.1" /usr/lib/x86_64-linux-gnu/webkit2gtk-4.1 2>/dev/null || true
if [ "$DISPLAY" = ":98" ] && [ ! -e /tmp/.X11-unix/X98 ]; then
  Xvfb :98 -screen 0 1920x1080x24 >>"$BASE/xvfb.log" 2>&1 &
  sleep 2
fi
exec dbus-run-session -- "$BASE/deb-root/usr/bin/cockpit-tools" >>"$BASE/app.log" 2>&1
