from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Tuple

try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore


# Defaults used if no config file is present
_DEFAULT_AXES: Tuple[str, ...] = (
    "COMPONENT",
    "PROPERTY",
    "TIME_ASPCT",
    "SYSTEM",
    "SCALE_TYP",
    "METHOD_TYP",
    "CLASS_TYPE_DESC"
)


def _project_root() -> Path:
    # src/annot_aid/config.py -> project root is two parents up
    return Path(__file__).resolve().parents[2]


def _load_toml_config() -> Dict[str, Any]:
    cfg_path = _project_root() / "config.toml"
    if not cfg_path.exists() or tomllib is None:
        return {}
    try:
        data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        # On malformed config, fall back to defaults silently for robustness
        return {}


def get_config() -> Dict[str, Any]:
    """Return the merged runtime config with safe defaults.

    Structure:
    {
      "annot_aid": {
          "axes": ["Component", ...]
      }
    }
    """
    data = _load_toml_config()
    aa = data.get("annot_aid", {}) if isinstance(data, dict) else {}
    loinc_axes = aa.get("loinc_axes") if isinstance(aa, dict) else None
    if not isinstance(loinc_axes, list) or not all(isinstance(x, str) for x in loinc_axes):
        axes = list(_DEFAULT_AXES)
    return {"annot_aid": {"loinc_axes": loinc_axes}}


# Public constant used across the app
AXES: Tuple[str, ...] = tuple(get_config()["annot_aid"]["loinc_axes"])  # type: ignore[index]
