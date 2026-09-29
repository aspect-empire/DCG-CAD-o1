from gencore.cad_operations import (
    CadOperation,
    CadOperationKind,
    CadOperationResult,
)


def operation():
    return CadOperation.create(
        CadOperationKind.UPDATE_PARAMETERS,
        run_id="run-1",
        graph_version="ver:1",
        model_version="model:1",
        targets=("foundation:1",),
        parameters={"panel_thickness_mm": "8"},
        required_validations=("model_update", "interference"),
    )


def test_same_operation_and_input_version_share_idempotency_key():
    values = dict(
        kind=CadOperationKind.UPDATE_PARAMETERS,
        run_id="run-1",
        graph_version="ver:1",
        model_version="model:1",
        targets=("foundation:1",),
        parameters={"panel_thickness_mm": "8"},
    )
    first = CadOperation.create(
        CadOperationKind.UPDATE_PARAMETERS,
        run_id="run-1",
        graph_version="ver:1",
        model_version="model:1",
        targets=("foundation:1",),
        parameters={"panel_thickness_mm": "8"},
    )
    second = CadOperation.create(**values)

    assert first == second
    assert first.idempotency_key == second.idempotency_key
    assert first.operation_id.startswith("cadop:")


def test_changed_input_version_changes_idempotency_key():
    first = operation()
    second = CadOperation.create(
        CadOperationKind.UPDATE_PARAMETERS,
        run_id="run-1",
        graph_version="ver:2",
        model_version="model:1",
        targets=("foundation:1",),
        parameters={"panel_thickness_mm": "8"},
        required_validations=("model_update", "interference"),
    )

    assert first.idempotency_key != second.idempotency_key


def test_operation_result_preserves_versions_geometry_changes_and_validation():
    source = operation()
    result = CadOperationResult.from_operation(
        source,
        status="completed",
        backend="CATIA",
        affected_objects=("foundation:1",),
        geometry_reference_changes=(
            {"reference_id": "face:mount", "new_locator": "BRep:face:7"},
        ),
        artifact_refs=(
            {
                "artifact_id": "model:step",
                "locator": "runs/outputs/run-1/base.step",
                "sha256": "a" * 64,
            },
        ),
        logs=("CATIA update completed",),
    )

    payload = result.to_dict()
    assert payload["graph_version"] == "ver:1"
    assert payload["model_version"] == "model:1"
    assert payload["required_validations"] == ["model_update", "interference"]
    assert payload["geometry_reference_changes"][0]["reference_id"] == "face:mount"


def test_all_required_staged_operation_kinds_are_declared():
    assert {item.value for item in CadOperationKind} >= {
        "probe_session",
        "build_compartment_scene",
        "create_foundation",
        "update_parameters",
        "update_holes",
        "update_gussets",
        "assemble_foundation",
        "update_model",
        "export",
        "check_interference",
        "relocate_references",
        "create_recovery_point",
        "rollback",
    }
