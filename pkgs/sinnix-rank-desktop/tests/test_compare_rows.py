from main import compare_rows, projection_label


def stats(**values):
    return {"stats": {"size": 0, "duration": 0, "pixels": 0, "bitrate": 0, "codec": "",
                      "projection": "", "plays": 0, **values}}


def test_pair_facts_mark_the_stronger_value_and_skip_missing_rows():
    left = stats(size=32 * 2**30, duration=4540, pixels=8192 * 4096, width=8192, height=4096,
                 bitrate=60e6, codec="HEVC", projection="180° side by side", plays=2)
    right = stats(size=29 * 2**30, duration=4680, pixels=5760 * 2880, width=5760, height=2880,
                  bitrate=53e6, codec="H264", projection="180° side by side", plays=0)
    rows = {row["label"]: row for row in compare_rows(left, right)}
    assert rows["Size"]["winner"] == "left"
    assert rows["Length"]["winner"] == "right"
    assert rows["Resolution"]["left"] == "8192 × 4096"
    assert rows["Bitrate"]["right"] == "53 Mb/s"
    assert rows["Codec"]["winner"] == "" and rows["Plays"]["winner"] == ""
    assert "Projection" in rows

    assert compare_rows(stats(size=1), stats()) == [
        {"label": "Size", "left": "1 B", "right": "—", "winner": ""},
    ]


def test_projection_labels_name_the_lens_and_layout():
    assert projection_label({"projection": "equirect", "layout": "sbs", "hfov": 180}) == "180° side by side"
    assert projection_label({"projection": "fisheye", "layout": "sbs", "hfov": 200}) == "Fisheye 200° side by side"
    assert projection_label({"projection": "unknown"}) == "Not set"
    assert projection_label({}) == ""


def test_sitting_tally_counts_choices_undo_and_freed_space():
    from dataclasses import replace
    from types import SimpleNamespace
    from main import Controller
    from session import Item

    controller = Controller()
    try:
        big = Item("1", "Scene_A.mp4", size=3 * 2**30, versions=({"id": "9", "basename": "Scene_A_copy.mp4", "size": 2**30},))
        small = Item("2", "Scene_B.mp4", size=2**30)
        # After the delete the library reloads without Scene B and A's copy.
        controller._session = SimpleNamespace(items={"1": replace(big, versions=())})
        controller._record({"action": "left", "pair": [big, small], "ids": [], "sizes": {}})
        controller._record({"action": "undo", "pair": [big, small], "ids": [], "sizes": {}})
        assert controller._tally["compared"] == 0 and controller._recent == []
        sizes = controller._sizes([big, small], ["2", "9"])
        controller._record({"action": "delete", "pair": [big, small], "ids": ["2", "9"], "sizes": sizes})
        assert controller.tally == {"compared": 0, "deleted": 2, "freed": 2 * 2**30, "freed_label": "2.00 GiB"}
        assert [entry["text"] for entry in controller.recent] == [
            "Deleted Scene A copy · 1.00 GiB", "Deleted Scene B · 1.00 GiB"]
    finally:
        controller._session = None
        controller.close()
