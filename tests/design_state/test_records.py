from types import MappingProxyType

import pytest

from gencore.design_state import DesignNode, EvidenceRef, ValueState, View


def test_node_is_content_addressed_and_view_typed():
    evidence = EvidenceRef("artifact:rule-02", "docx", "p:307", "a" * 64)
    first = DesignNode.create(
        View.PARAMETER_RULE,
        "Parameter",
        "基座:板厚",
        {"name": "板厚"},
        [evidence],
    )
    second = DesignNode.create(
        View.PARAMETER_RULE,
        "Parameter",
        "基座:板厚",
        {"name": "板厚"},
        [evidence],
    )

    assert first.uid == second.uid
    assert first.state is ValueState.OBSERVED
    assert first.to_dict() == second.to_dict()


def test_unknown_node_requires_missing_inputs():
    with pytest.raises(ValueError, match="missing_inputs"):
        DesignNode.create(
            View.PARAMETER_RULE,
            "ParameterValue",
            "基座:板厚:v1",
            {},
            [],
            state=ValueState.UNKNOWN,
        )


def test_evidence_digest_must_be_hexadecimal():
    with pytest.raises(ValueError, match="hexadecimal"):
        EvidenceRef("artifact:rule-02", "docx", "p:307", "z" * 64)


def test_nested_attributes_are_recursively_immutable():
    node = DesignNode.create(
        View.GEOMETRY_SPATIAL,
        "Boundary",
        "基座:安装面",
        {"signature": {"normal": [0, 0, 1]}},
        [],
    )

    assert isinstance(node.attributes, MappingProxyType)
    with pytest.raises(TypeError):
        node.attributes["signature"]["normal"] = (1, 0, 0)
    assert node.to_dict()["attributes"]["signature"]["normal"] == [0, 0, 1]
