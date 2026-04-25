from __future__ import annotations

CONTROL_CENTER_VERSION = "2"


def config_has_usable_routine(config_data: dict) -> bool:
    routines = (config_data or {}).get("routines", {})
    if not isinstance(routines, dict) or not routines:
        return False
    for routine in routines.values():
        if isinstance(routine, dict) and routine.get("items"):
            return True
    return False


def should_show_first_run(config_data: dict) -> bool:
    system = (config_data or {}).get("system", {})
    if not isinstance(system, dict):
        return True
    if not system.get("first_run_completed", False):
        return True
    return not config_has_usable_routine(config_data)


def mark_first_run_completed(config_data: dict) -> None:
    system = config_data.setdefault("system", {})
    system["first_run_completed"] = True
    system["last_control_center_version"] = CONTROL_CENTER_VERSION


def ensure_first_run_metadata(config_data: dict) -> None:
    system = config_data.setdefault("system", {})
    system.setdefault("first_run_completed", False)
    system.setdefault("last_control_center_version", CONTROL_CENTER_VERSION)
