import pytest

from tests.conftest import TestingSessionLocal, make_user_client

PLAYER_VK = 123


def _make_barnyard_field(admin_client, cols=2, rows=2, paint=((0, 0),)):
    fid = admin_client.post(
        "/api/admin/fields", json={"name": "Скотный", "cols": cols, "rows": rows, "field_kind": "barnyard"}
    ).json()["id"]
    admin_client.put(
        f"/api/admin/fields/{fid}/cells/blocked",
        json={"cells": [{"col": c, "row": r} for c, r in paint], "kind": "barnyard"},
    )
    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    cells = {(c["col"], c["row"]): c for c in detail["cells"]}
    return fid, cells


def _seed_slot(vk_id, animal_id=1, cell_id=None, status="ready"):
    from models import BarnyardSlot
    s = TestingSessionLocal()
    try:
        slot = BarnyardSlot(
            user_id=vk_id, animal_id=animal_id, cell_id=cell_id,
            status=status, accumulated=0, required=0,
        )
        s.add(slot)
        s.commit()
        s.refresh(slot)
        return slot.id
    finally:
        s.close()


def _slot_ids(vk_id):
    from models import BarnyardSlot
    s = TestingSessionLocal()
    try:
        return sorted(r[0] for r in s.query(BarnyardSlot.id).filter(BarnyardSlot.user_id == vk_id).all())
    finally:
        s.close()


def test_install_purges_ghost_slot(admin_client):
    fid, cells = _make_barnyard_field(admin_client)
    cell_id = cells[(0, 0)]["id"]

    _seed_slot(PLAYER_VK, animal_id=1, cell_id=None)

    with make_user_client(PLAYER_VK, "player") as pc:
        res = pc.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1})
        assert res.status_code == 200, res.text
        new_id = res.json()["id"]
    assert _slot_ids(PLAYER_VK) == [new_id]


def test_field_detail_purges_ghost_slots(admin_client):
    fid, cells = _make_barnyard_field(admin_client, paint=[(0, 0), (1, 1)])
    in_grid = cells[(0, 0)]["id"]

    s = TestingSessionLocal()
    try:
        from models import Field, FieldCell, BarnyardSlot
        f = s.query(Field).filter(Field.id == fid).first()
        out_cell = FieldCell(field_id=f.id, col=5, row=5, kind="barnyard")
        s.add(out_cell)
        s.flush()
        bed_cell = s.query(FieldCell).filter(
            FieldCell.field_id == f.id, FieldCell.col == 1, FieldCell.row == 0
        ).first()
        bed_cell.kind = "bed"
        s.flush()
        s.add(BarnyardSlot(user_id=PLAYER_VK, animal_id=1, cell_id=in_grid, status="ready"))
        s.add(BarnyardSlot(user_id=PLAYER_VK, animal_id=1, cell_id=None, status="ready"))
        s.add(BarnyardSlot(user_id=PLAYER_VK, animal_id=2, cell_id=out_cell.id, status="ready"))
        s.add(BarnyardSlot(user_id=PLAYER_VK, animal_id=2, cell_id=bed_cell.id, status="ready"))
        s.commit()
        valid_id = s.query(BarnyardSlot).filter(BarnyardSlot.cell_id == in_grid).first().id
    finally:
        s.close()

    with make_user_client(PLAYER_VK, "player") as pc:
        res = pc.get(f"/api/fields/{fid}")
        assert res.status_code == 200, res.text
    assert _slot_ids(PLAYER_VK) == [valid_id]


def test_release_pen_frees_animal(admin_client):
    fid, cells = _make_barnyard_field(admin_client)
    cell_id = cells[(0, 0)]["id"]

    with make_user_client(PLAYER_VK, "player") as pc:
        slot = pc.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1}).json()
        res = pc.delete(f"/api/animals/pens/{slot['id']}")
        assert res.status_code == 204, res.text

        again = pc.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1})
        assert again.status_code == 200, again.text
    assert _slot_ids(PLAYER_VK) == [again.json()["id"]]


def test_release_pen_other_user_404(admin_client):
    fid, cells = _make_barnyard_field(admin_client)
    cell_id = cells[(0, 0)]["id"]

    with make_user_client(PLAYER_VK, "player") as pc:
        slot = pc.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1}).json()
    with make_user_client(124, "player") as other:
        res = other.delete(f"/api/animals/pens/{slot['id']}")
    assert res.status_code == 404
    assert _slot_ids(PLAYER_VK) == [slot["id"]]


def test_release_pen_unknown_404(player_client):
    assert player_client.delete("/api/animals/pens/99999").status_code == 404


def test_admin_player_detail_lists_barnyard(admin_client):
    fid, cells = _make_barnyard_field(admin_client)
    cell_id = cells[(0, 0)]["id"]
    with make_user_client(PLAYER_VK, "player") as pc:
        pc.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1})
    ghost_id = _seed_slot(PLAYER_VK, animal_id=2, cell_id=None)

    res = admin_client.get(f"/api/admin/players/{PLAYER_VK}")
    assert res.status_code == 200, res.text
    pens = {b["id"]: b for b in res.json()["barnyard"]}
    assert ghost_id in pens
    assert len(pens) == 2
    assert pens[ghost_id]["is_ghost"] is True
    valid = [b for b in pens.values() if not b["is_ghost"]]
    assert len(valid) == 1
    assert valid[0]["animal_name"] == "Ватная овечка"
    assert valid[0]["cell_col"] == 0 and valid[0]["cell_row"] == 0


def test_admin_delete_player_barnyard_slot(admin_client):
    fid, cells = _make_barnyard_field(admin_client)
    cell_id = cells[(0, 0)]["id"]
    with make_user_client(PLAYER_VK, "player") as pc:
        slot = pc.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1}).json()

    res = admin_client.delete(f"/api/admin/players/{PLAYER_VK}/barnyard/{slot['id']}")
    assert res.status_code == 204, res.text
    assert _slot_ids(PLAYER_VK) == []

    assert admin_client.delete(f"/api/admin/players/{PLAYER_VK}/barnyard/{slot['id']}").status_code == 404
    assert admin_client.delete(f"/api/admin/players/{PLAYER_VK}/barnyard/99999").status_code == 404


def test_admin_delete_player_barnyard_requires_admin(player_client):
    assert player_client.delete(f"/api/admin/players/{PLAYER_VK}/barnyard/1").status_code == 403


def test_set_cell_kind_blocked_when_pen_occupied(admin_client):
    fid, cells = _make_barnyard_field(admin_client)
    cell_id = cells[(0, 0)]["id"]
    with make_user_client(PLAYER_VK, "player") as pc:
        pc.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1})

    res = admin_client.put(f"/api/admin/fields/{fid}/cell/0/0", json={"kind": "bed"})
    assert res.status_code == 409, res.text

    with make_user_client(PLAYER_VK, "player") as pc:
        pc.delete(f"/api/animals/pens/{_slot_ids(PLAYER_VK)[0]}")
    res = admin_client.put(f"/api/admin/fields/{fid}/cell/0/0", json={"kind": "bed"})
    assert res.status_code == 200, res.text


def test_bulk_cells_out_of_bounds_400(admin_client):
    fid, _ = _make_barnyard_field(admin_client)
    res = admin_client.put(
        f"/api/admin/fields/{fid}/cells/blocked",
        json={"cells": [{"col": 99, "row": 0}], "kind": "barnyard"},
    )
    assert res.status_code == 400, res.text


def test_bulk_cells_blocked_when_pen_occupied(admin_client):
    fid, cells = _make_barnyard_field(admin_client, paint=[(0, 0), (1, 0)])
    cell_id = cells[(0, 0)]["id"]
    with make_user_client(PLAYER_VK, "player") as pc:
        pc.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1})

    res = admin_client.put(
        f"/api/admin/fields/{fid}/cells/blocked",
        json={"cells": [{"col": 1, "row": 0}], "kind": "barnyard"},
    )
    assert res.status_code == 409, res.text
