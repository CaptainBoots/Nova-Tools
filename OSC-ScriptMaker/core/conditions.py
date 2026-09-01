"""
core/conditions.py
───────────────────
Pure value casting + condition evaluation. No Qt, no OSC — trivially
testable by calling functions directly.
"""

from __future__ import annotations


def cast_value(raw):
    """Best-effort cast of an OSC/variable value or a stringly-typed
    comparison box into a Python bool/int/float/str."""
    if isinstance(raw, (bool, int, float)):
        return raw
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "":
        return ""
    low = s.lower()
    if low in ("true", "on", "yes"):
        return True
    if low in ("false", "off", "no"):
        return False
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s


def _truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.lower() in ("true", "on", "yes", "1")
    return bool(v)


def _numeric(v):
    v = cast_value(v)
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    return None


def evaluate_condition(condition: str, new_value, cmp_value="", cmp_value2="",
                        prev_value=None) -> bool:
    """Returns True if `condition` fires given the new incoming value,
    the trigger's configured comparison value(s), and the previously
    seen value for this same address/variable (None if never seen)."""
    if condition == "any":
        return True

    if condition == "changed":
        if prev_value is None:
            return False
        return cast_value(new_value) != cast_value(prev_value)

    if condition == "rising_edge":
        if prev_value is None:
            return False
        return (not _truthy(prev_value)) and _truthy(new_value)

    if condition == "falling_edge":
        if prev_value is None:
            return False
        return _truthy(prev_value) and (not _truthy(new_value))

    if condition == "equals":
        return cast_value(new_value) == cast_value(cmp_value)

    if condition == "not_equals":
        return cast_value(new_value) != cast_value(cmp_value)

    if condition in ("greater", "less", "in_range"):
        nv = _numeric(new_value)
        if nv is None:
            return False
        if condition == "greater":
            cv = _numeric(cmp_value)
            return cv is not None and nv > cv
        if condition == "less":
            cv = _numeric(cmp_value)
            return cv is not None and nv < cv
        # in_range
        lo = _numeric(cmp_value)
        hi = _numeric(cmp_value2)
        if lo is None or hi is None:
            return False
        if lo > hi:
            lo, hi = hi, lo
        return lo <= nv <= hi

    return False


def remap(value, in_min: float, in_max: float, out_min: float, out_max: float,
          invert: bool = False) -> float:
    """Linear remap of `value` from [in_min, in_max] to [out_min, out_max],
    clamped to the input range first. `invert` flips the output direction
    within [out_min, out_max]."""
    nv = _numeric(value)
    if nv is None:
        nv = 0.0
    if in_max == in_min:
        frac = 0.0
    else:
        nv = max(min(nv, max(in_min, in_max)), min(in_min, in_max))
        frac = (nv - in_min) / (in_max - in_min)
    if invert:
        frac = 1.0 - frac
    return out_min + frac * (out_max - out_min)
