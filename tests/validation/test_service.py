from gencore.validation import REQUIRED_CHECK_KINDS, ValidationService


def test_cad_success_text_without_checks_does_not_pass():
    result = ValidationService().evaluate(
        plan={
            "checks": [
                {"check_id": "open", "kind": "model_openable", "required": True},
                {
                    "check_id": "export",
                    "kind": "model_exportable",
                    "required": True,
                },
            ]
        },
        tool_results=[{"status": "completed", "message": "success"}],
        graph_snapshot={},
    )

    assert result.status == "incomplete"
    assert "model_openable" in result.missing_checks
    assert result.coverage == 0.0


def test_interference_failure_invalidates_only_declared_affected_objects():
    result = ValidationService().evaluate(
        plan={
            "checks": [
                {"check_id": "clash", "kind": "interference", "required": True},
            ]
        },
        tool_results=[
            {
                "check_id": "clash",
                "status": "failed",
                "changed_uids": ["constraint:clearance"],
                "dependencies": {
                    "constraint:clearance": ["parameter:offset"],
                    "parameter:offset": ["feature:hole"],
                },
                "evidence_refs": ["artifact:clash-report"],
                "tool_id": "geometry.cad.check_interference",
                "model_version": "model:2",
            }
        ],
        graph_snapshot={"nodes": {"unrelated:paint": {"state": "verified"}}},
    )

    assert result.status == "failed"
    assert result.affected_uids == (
        "constraint:clearance",
        "feature:hole",
        "parameter:offset",
    )
    assert "unrelated:paint" not in result.affected_uids
    assert result.findings[0].recommended_action == "repair_and_revalidate"


def test_required_check_needs_independent_evidence_to_pass():
    result = ValidationService().evaluate(
        plan={
            "checks": [
                {"check_id": "open", "kind": "model_openable", "required": True}
            ]
        },
        tool_results=[
            {
                "check_id": "open",
                "status": "passed",
                "tool_id": "geometry.cad.probe",
                "model_version": "model:1",
                "evidence_refs": ["artifact:probe-report"],
            }
        ],
        graph_snapshot={},
    )

    assert result.status == "passed"
    assert result.coverage == 1.0
    assert result.findings[0].state == "passed"


def test_catia_and_interference_payloads_become_graph_proposals():
    result = ValidationService().evaluate(
        plan={
            "run_id": "validate-1",
            "base_version": "ver:base",
            "checks": [
                {
                    "check_id": "export",
                    "kind": "model_exportable",
                    "required": True,
                }
            ],
        },
        tool_results=[
            {
                "check_id": "export",
                "status": "passed",
                "tool_id": "geometry.cad.export",
                "model_version": "model:2",
                "evidence_refs": ["artifact:cad-manifest"],
                "catia_manifest": {
                    "run_id": "validate-1",
                    "execution_id": "export-1",
                    "stage": "export",
                    "status": "completed",
                    "artifact_id": "artifact:cad-manifest",
                    "sha256": "a" * 64,
                    "artifacts": [],
                },
            }
        ],
        graph_snapshot={},
    )

    assert len(result.graph_proposals) == 1
    assert result.graph_proposals[0]["base_version"] == "ver:base"


def test_validation_catalog_covers_engineering_and_evidence_checks():
    assert {
        "model_exists",
        "model_openable",
        "model_updateable",
        "model_exportable",
        "topology_validity",
        "feature_validity",
        "parameter_compliance",
        "rule_compliance",
        "installation_reference",
        "hole_constraints",
        "gusset_constraints",
        "clearance",
        "accessibility",
        "interference",
        "critical_unknown_scan",
        "conflict_scan",
        "provenance_coverage",
        "evidence_coverage",
    } <= REQUIRED_CHECK_KINDS
