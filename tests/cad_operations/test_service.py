from gencore.cad_operations import CadOperation, CadOperationKind
from gencore.cad_operations.service import CadOperationService, OptionalCatiaBackend


class FakeBackend:
    name = "CATIA-fake"

    def __init__(self):
        self.calls = []

    def apply_parametric_model_update(self, payload):
        self.calls.append(("apply_parametric_model_update", payload))
        return {
            "status": "completed",
            "affected_objects": ["foundation:1"],
            "artifacts": [],
        }

    def update_holes(self, payload):
        self.calls.append(("update_holes", payload))
        return {"success": False, "errors": ["hole reference missing"]}

    def create_foundation(self, payload):
        self.calls.append(("create_foundation", payload))
        return {"status": "completed", "affected_objects": ["foundation:1"]}


def update_operation():
    return CadOperation.create(
        kind=CadOperationKind.UPDATE_PARAMETERS,
        run_id="run-1",
        graph_version="ver:1",
        model_version="model:1",
        targets=("foundation:1",),
        parameters={"panel_thickness_mm": "8"},
        required_validations=("model_update", "interference"),
    )


def test_update_parameters_delegates_to_migrated_function_once(tmp_path):
    fake_backend = FakeBackend()
    service = CadOperationService(fake_backend, workspace_root=tmp_path)

    first = service.execute(update_operation(), approved=True)
    second = service.execute(update_operation(), approved=True)

    assert first.status == "completed"
    assert second == first
    assert [item[0] for item in fake_backend.calls] == [
        "apply_parametric_model_update"
    ]
    assert fake_backend.calls[0][1]["parameters"]["panel_thickness_mm"] == "8"


def test_cad_write_is_blocked_without_approval_and_can_run_later(tmp_path):
    fake_backend = FakeBackend()
    service = CadOperationService(fake_backend, workspace_root=tmp_path)

    blocked = service.execute(update_operation(), approved=False)
    completed = service.execute(update_operation(), approved=True)

    assert blocked.status == "approval_required"
    assert fake_backend.calls
    assert completed.status == "completed"


def test_backend_failure_and_exception_are_always_structured(tmp_path):
    fake_backend = FakeBackend()
    service = CadOperationService(fake_backend, workspace_root=tmp_path)
    holes = CadOperation.create(
        CadOperationKind.UPDATE_HOLES,
        run_id="run-2",
        graph_version="ver:1",
        model_version="model:1",
        targets=("foundation:1",),
        parameters={"holes": []},
    )
    failed = service.execute(holes, approved=True)

    class RaisingBackend:
        def apply_parametric_model_update(self, payload):
            raise RuntimeError("CATIA session disconnected")

    raised = CadOperationService(
        RaisingBackend(), workspace_root=tmp_path / "raising"
    ).execute(update_operation(), approved=True)

    assert failed.status == "failed"
    assert failed.failure_class == "backend_failure"
    assert "hole reference missing" in failed.logs
    assert raised.status == "failed"
    assert raised.failure_class == "RuntimeError"
    assert "CATIA session disconnected" in raised.logs


def test_probe_is_read_only_and_does_not_require_write_approval(tmp_path):
    class ProbeBackend:
        def __init__(self):
            self.calls = 0

        def probe_session(self, payload):
            self.calls += 1
            return {"status": "completed", "backend": "CATIA", "available": True}

    backend = ProbeBackend()
    operation = CadOperation.create(
        CadOperationKind.PROBE_SESSION,
        run_id="probe-1",
        graph_version="ver:1",
        model_version="model:none",
        targets=(),
    )

    result = CadOperationService(backend, workspace_root=tmp_path).execute(
        operation, approved=False
    )

    assert result.status == "completed"
    assert backend.calls == 1


def test_backend_payload_deeply_thaws_nested_options(tmp_path):
    backend = FakeBackend()
    operation = CadOperation.create(
        CadOperationKind.CREATE_FOUNDATION,
        run_id="live-1",
        graph_version="ver:1",
        model_version="LT:template",
        targets=("foundation:LT",),
        options={
            "upstream": {
                "基座1": {"面板": {"外形尺寸": {"长度": 628}}},
            }
        },
    )

    result = CadOperationService(backend, workspace_root=tmp_path).execute(
        operation, approved=True
    )

    payload = backend.calls[0][1]
    assert result.status == "completed"
    assert type(payload["upstream"]) is dict
    assert type(payload["upstream"]["基座1"]) is dict
    assert type(payload["upstream"]["基座1"]["面板"]) is dict


def test_optional_catia_backend_uses_packaged_scene_generator(monkeypatch, tmp_path):
    calls = []

    def fake_build(config, output_path, visible=True):
        calls.append((config, output_path, visible))
        return output_path

    monkeypatch.setattr(
        "gencore.scene_generator.catia_api.scene_builder.build_catia_scene",
        fake_build,
    )
    target = tmp_path / "scene.CATProduct"
    result = OptionalCatiaBackend().build_compartment_scene(
        {"config": {"scene_id": "synthetic"}, "output_path": str(target), "visible": False}
    )

    assert result["status"] == "completed"
    assert result["exported_files"] == {"CATProduct": str(target)}
    assert calls == [({"scene_id": "synthetic"}, str(target), False)]
