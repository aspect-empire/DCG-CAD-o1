import json

import pytest

from gencore.tool_registry import ToolRegistry, ToolSpec, build_default_registry


def _spec(name="demo", *, risk_level="read_only", handler=lambda payload: {"echo": payload}):
    return ToolSpec(
        name=name,
        description="A deterministic test tool.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        risk_level=risk_level,
        execution_mode="offline",
        handler=handler,
    )


def test_registry_rejects_duplicate_names_and_invalid_contract_values():
    registry = ToolRegistry([_spec()])
    with pytest.raises(ValueError, match="duplicate"):
        registry.register(_spec())
    with pytest.raises(ValueError, match="risk_level"):
        _spec(risk_level="unsafe")


def test_registry_lists_json_serializable_metadata_without_handlers():
    metadata = ToolRegistry([_spec()]).list_tools()
    assert metadata == [
        {
            "name": "demo",
            "description": "A deterministic test tool.",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "risk_level": "read_only",
            "execution_mode": "offline",
        }
    ]
    json.dumps(metadata)


def test_registry_invoke_requires_dict_input_and_dict_json_output():
    registry = ToolRegistry([_spec()])
    assert registry.invoke("demo", {"value": 3}) == {"echo": {"value": 3}}
    with pytest.raises(TypeError, match="dict"):
        registry.invoke("demo", ["not", "a", "dict"])
    with pytest.raises(TypeError, match="dict"):
        ToolRegistry([_spec(handler=lambda payload: "not a dict")]).invoke("demo", {})
    with pytest.raises(ValueError, match="JSON-serializable"):
        ToolRegistry([_spec(handler=lambda payload: {"bad": object()})]).invoke("demo", {})


def test_default_registry_has_unique_names_and_normalized_contracts():
    metadata = build_default_registry().list_tools()
    names = [item["name"] for item in metadata]
    assert len(names) == len(set(names))
    assert {
        "graph.ingest",
        "graph.build",
        "graph.query_affected",
        "skill.evaluate_candidate",
        "foundation.case_matching.match",
        "foundation.parameters.calculate",
        "orchestration.state.inspect",
        "orchestration.tasks.preview",
    } <= set(names)
    json.dumps(metadata)
