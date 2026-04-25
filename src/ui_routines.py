from __future__ import annotations

import copy
from typing import Dict, List


class RoutineStore:
    """State helper for routine item operations used by the settings UI."""

    def __init__(self, routines: Dict[str, dict], routine_name: str = "morning_routine"):
        self.routines = routines
        self.routine_name = routine_name

    def get_items(self) -> List[dict]:
        routine_data = self.routines.get(self.routine_name, {})
        items = routine_data.get("items", [])
        return items if isinstance(items, list) else []

    def set_items(self, items: List[dict]) -> None:
        routine_data = self.routines.setdefault(self.routine_name, {"items": []})
        routine_data["items"] = items

    def upsert_item(self, item: dict, index: int | None = None) -> None:
        items = self.get_items()
        if index is None:
            items.append(copy.deepcopy(item))
        else:
            items[index] = copy.deepcopy(item)
        self.set_items(items)

    def remove_by_indices(self, indices: List[int]) -> None:
        items = self.get_items()
        kept = [item for i, item in enumerate(items) if i not in set(indices)]
        self.set_items(kept)

    def reorder_by_previous_indices(self, previous_indices: List[int]) -> None:
        old_items = self.get_items()
        new_items = []
        for idx in previous_indices:
            if 0 <= idx < len(old_items):
                new_items.append(old_items[idx])
        self.set_items(new_items)

    def move_item(self, index: int, direction: int) -> int:
        """Move item by one slot and return the new index."""
        items = self.get_items()
        if not (0 <= index < len(items)):
            return index
        target_index = index + direction
        if not (0 <= target_index < len(items)):
            return index
        items[index], items[target_index] = items[target_index], items[index]
        self.set_items(items)
        return target_index

    def set_item_enabled(self, index: int, enabled: bool) -> bool:
        items = self.get_items()
        if not (0 <= index < len(items)):
            return False
        items[index] = copy.deepcopy(items[index])
        items[index]["enabled"] = bool(enabled)
        self.set_items(items)
        return True

    def toggle_item_enabled(self, index: int) -> bool | None:
        items = self.get_items()
        if not (0 <= index < len(items)):
            return None
        current = bool(items[index].get("enabled", True))
        enabled = not current
        self.set_item_enabled(index, enabled)
        return enabled
