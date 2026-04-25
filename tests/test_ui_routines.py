from src.ui_routines import RoutineStore


def _make_routines():
    return {
        "morning_routine": {
            "items": [
                {"name": "A", "type": "app", "target": "a"},
                {"name": "B", "type": "app", "target": "b"},
                {"name": "C", "type": "app", "target": "c"},
            ]
        }
    }


def test_upsert_add_and_edit_item():
    routines = _make_routines()
    store = RoutineStore(routines)
    store.upsert_item({"name": "D", "type": "app", "target": "d"})
    assert [i["name"] for i in store.get_items()] == ["A", "B", "C", "D"]

    store.upsert_item({"name": "B2", "type": "app", "target": "b2"}, index=1)
    assert [i["name"] for i in store.get_items()] == ["A", "B2", "C", "D"]


def test_remove_by_indices():
    routines = _make_routines()
    store = RoutineStore(routines)
    store.remove_by_indices([0, 2])
    assert [i["name"] for i in store.get_items()] == ["B"]


def test_reorder_by_previous_indices():
    routines = _make_routines()
    store = RoutineStore(routines)
    store.reorder_by_previous_indices([2, 0, 1])
    assert [i["name"] for i in store.get_items()] == ["C", "A", "B"]


def test_move_item_up_and_down():
    routines = _make_routines()
    store = RoutineStore(routines)
    new_idx = store.move_item(1, -1)
    assert new_idx == 0
    assert [i["name"] for i in store.get_items()] == ["B", "A", "C"]

    new_idx = store.move_item(0, 1)
    assert new_idx == 1
    assert [i["name"] for i in store.get_items()] == ["A", "B", "C"]


def test_move_item_edges_do_not_change_order():
    routines = _make_routines()
    store = RoutineStore(routines)
    assert store.move_item(0, -1) == 0
    assert store.move_item(2, 1) == 2
    assert store.move_item(99, 1) == 99
    assert [i["name"] for i in store.get_items()] == ["A", "B", "C"]


def test_toggle_item_enabled():
    routines = _make_routines()
    store = RoutineStore(routines)
    assert store.toggle_item_enabled(1) is False
    assert store.get_items()[1]["enabled"] is False
    assert store.toggle_item_enabled(1) is True
    assert store.get_items()[1]["enabled"] is True
    assert store.toggle_item_enabled(99) is None
