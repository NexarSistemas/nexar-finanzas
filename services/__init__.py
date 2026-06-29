"""
Compatibilidad entre el modulo legado services.py y el paquete services.
"""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_LEGACY_SERVICES_PATH = Path(__file__).resolve().parent.parent / "services.py"
_LEGACY_SPEC = spec_from_file_location("_legacy_services_module", _LEGACY_SERVICES_PATH)

if _LEGACY_SPEC is not None and _LEGACY_SPEC.loader is not None:
    _legacy_services = module_from_spec(_LEGACY_SPEC)
    _LEGACY_SPEC.loader.exec_module(_legacy_services)

    for _name in dir(_legacy_services):
        if _name.startswith("_"):
            continue
        globals()[_name] = getattr(_legacy_services, _name)


from . import financial_health
