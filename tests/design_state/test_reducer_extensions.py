from gencore.design_state.proposals import GraphOperation
from gencore.design_state.reducer import reduce_operations


def snapshot():
    return {
        "nodes": {
            "node:a": {
                "uid": "node:a",
                "state": "observed",
                "attributes": {"height_mm": "100"},
            }
        },
        "edges": {},
    }


def test_update_attributes_merges_without_removing_existing_values():
    result = reduce_operations(
        snapshot(),
        (
            GraphOperation(
                "update_attributes",
                "node:a",
                {"attributes": {"width_mm": "200"}},
            ),
        ),
    )

    assert result["nodes"]["node:a"]["attributes"] == {
        "height_mm": "100",
        "width_mm": "200",
    }


def test_bind_reference_records_reference_and_state():
    result = reduce_operations(
        snapshot(),
        (
            GraphOperation(
                "bind_reference",
                "node:a",
                {
                    "reference": {
                        "persistent_uri": "catia://part/face/1",
                        "state": "stable",
                    }
                },
            ),
        ),
    )

    assert result["nodes"]["node:a"]["geometry_reference"]["state"] == "stable"
