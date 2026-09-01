"""monitors/steamvr.py — polls SteamVR via openvr."""
import ctypes
import threading
import time

try:
    import openvr
    _HAS_OPENVR = True
except ImportError:
    _HAS_OPENVR = False

_data = {
    "vr_fps":              None,
    "vr_frametimes":       None,
    "vr_reprojection":     None,
    "vr_headset":          None,
    "vr_connected":        False,
    "vr_hmd_battery":      None,
    "vr_hmd_charging":     None,
    "vr_lc_battery":       None,
    "vr_lc_charging":      None,
    "vr_rc_battery":       None,
    "vr_rc_charging":      None,
    "vr_trackers":         [],   # list of {"battery": int|None, "charging": bool|None}
}
_lock    = threading.Lock()
_started = False

def _pct(val) -> int | None:
    try:
        f = float(val)
        if f <= 0.0:
            return None
        return max(0, min(100, int(f * 100)))
    except Exception:
        return None

def _get_battery(vrsys, idx):
    """Returns (battery_pct, is_charging) or (None, None) if unsupported."""
    try:
        batt = vrsys.getFloatTrackedDeviceProperty(
            idx, openvr.Prop_DeviceBatteryPercentage_Float)
        charging = vrsys.getBoolTrackedDeviceProperty(
            idx, openvr.Prop_DeviceIsCharging_Bool)
        return _pct(batt), bool(charging)
    except Exception:
        return None, None

def _poll():
    initialized = False
    while True:
        try:
            if not initialized:
                openvr.init(openvr.VRApplication_Background)
                initialized = True

            vrsys  = openvr.VRSystem()
            comp   = openvr.VRCompositor()

            # ── FPS via frame timing ──────────────────────────────────────────
            # Use ctypes.sizeof, not openvr.sizeof (doesn't exist in Python bindings)
            # getFrameTiming returns (success, Compositor_FrameTiming)
            _, timing = comp.getFrameTiming(0)
            # m_flClientFrameIntervalMs is the actual wall-clock inter-frame
            # interval. m_flTotalRenderGpuMs is GPU-only and returns 0.0 when
            # the compositor is idle, which caused FPS to always read N/A.
            frame_ms = timing.m_flClientFrameIntervalMs
            fps = round(1000.0 / frame_ms, 1) if frame_ms > 0 else None

            # ── Reprojection ──────────────────────────────────────────────────
            stats = comp.getCumulativeStats(ctypes.sizeof(openvr.Compositor_CumulativeStats))
            total  = max(stats.m_nNumFramePresents, 1)
            reproj = round(stats.m_nNumReprojectedFrames / total, 2)

            # ── Headset name ──────────────────────────────────────────────────
            hmd_name = vrsys.getStringTrackedDeviceProperty(
                openvr.k_unTrackedDeviceIndex_Hmd,
                openvr.Prop_ModelNumber_String)

            # ── Headset battery ───────────────────────────────────────────────
            hmd_batt, hmd_chg = _get_battery(vrsys, openvr.k_unTrackedDeviceIndex_Hmd)

            # ── Controllers + trackers ────────────────────────────────────────
            lc_batt = lc_chg = rc_batt = rc_chg = None
            ctrl_found = 0
            trackers = []

            for i in range(1, openvr.k_unMaxTrackedDeviceCount):
                cls = vrsys.getTrackedDeviceClass(i)
                if cls == openvr.TrackedDeviceClass_Invalid:
                    continue
                if cls == openvr.TrackedDeviceClass_Controller:
                    b, c = _get_battery(vrsys, i)
                    if ctrl_found == 0:
                        lc_batt, lc_chg = b, c
                    elif ctrl_found == 1:
                        rc_batt, rc_chg = b, c
                    ctrl_found += 1
                elif cls == openvr.TrackedDeviceClass_GenericTracker:
                    b, c = _get_battery(vrsys, i)
                    trackers.append({"battery": b, "charging": c})

            with _lock:
                _data.update({
                    "vr_fps":          fps,
                    "vr_frametimes":   round(timing.m_flTotalRenderGpuMs, 1) if timing.m_flTotalRenderGpuMs > 0 else None,
                    "vr_reprojection": reproj,
                    "vr_headset":      hmd_name,
                    "vr_connected":    True,
                    "vr_hmd_battery":  hmd_batt,
                    "vr_hmd_charging": hmd_chg,
                    "vr_lc_battery":   lc_batt,
                    "vr_lc_charging":  lc_chg,
                    "vr_rc_battery":   rc_batt,
                    "vr_rc_charging":  rc_chg,
                    "vr_trackers":     trackers,
                })

        except Exception as e:
            if _data.get("vr_connected"):
                print(f"[steamvr monitor] error: {e}")
            with _lock:
                _data["vr_connected"] = False
            if initialized:
                try:
                    openvr.shutdown()
                except Exception:
                    pass
                initialized = False

        time.sleep(2)

def start():
    global _started
    if _started:
        return
    _started = True
    if not _HAS_OPENVR:
        print("[steamvr monitor] openvr not installed — VR modules will show N/A")
        return
    threading.Thread(target=_poll, daemon=True).start()

def snapshot() -> dict:
    with _lock:
        return dict(_data)