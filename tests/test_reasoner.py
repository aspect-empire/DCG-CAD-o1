from gencore.adapters import BasePipelineAdapter, TextAdapter
from gencore.graph import EngineeringGraph
from gencore.reasoner import GraphReasoner


def test_ex01_exact_parameter_fusion_preserves_failure():
    text = TextAdapter().adapt(run_id="EX-01", entity="肘板A", parameter="孔边距", value=8, unit="mm", raw_text="孔边距为8mm")[0]
    base = BasePipelineAdapter().adapt({"参数逐步生成表": [{"实体": "肘板A", "参数名": "孔边距", "参数值": 8, "单位": "mm"}], "校验结果": [{"校验项": "孔边距", "状态": "失败", "错误码": "EDGE_TOO_SMALL"}]}, run_id="EX-01")
    graph = EngineeringGraph().reduce([text, *base])
    result = GraphReasoner(graph).fuse_parameters()
    fused = next(item for item in result if item["parameter"] == "孔边距")
    assert fused["value"] == 8
    assert fused["unit"] == "mm"
    assert len(fused["premise_event_ids"]) == 2
    assert any(d["node_type"] == "FailureSignature" for _, d in graph.graph.nodes(data=True))
    derived = [d for *_, d in graph.graph.edges(data=True) if d["origin"] == "derived"]
    assert derived and derived[0]["derived_by"] == "parameter_evidence_fusion/v1"


def test_conflicting_evidence_and_affected_traversal():
    events = TextAdapter().adapt(run_id="R", entity="E", parameter="p", value=8, unit="mm", raw_text="8") + TextAdapter().adapt(run_id="R", entity="E", parameter="p", value=9, unit="mm", raw_text="9", sequence_start=2)
    graph = EngineeringGraph().reduce(events)
    fused = GraphReasoner(graph).fuse_parameters()[0]
    assert fused["status"] == "conflict"
    parameter = next(uid for uid, d in graph.graph.nodes(data=True) if d["node_type"] == "Parameter")
    assert parameter in GraphReasoner(graph).affected_subgraph(parameter)


def test_affected_traversal_does_not_cross_a_shared_task_hub():
    events = TextAdapter().adapt(run_id="shared", entity="E", parameter="p1", value=8, unit="mm", raw_text="8")
    events += TextAdapter().adapt(run_id="shared", entity="E", parameter="p2", value=9, unit="mm", raw_text="9", sequence_start=2)
    graph = EngineeringGraph().reduce(events)
    parameters = {data["name"]: uid for uid, data in graph.graph.nodes(data=True) if data["node_type"] == "Parameter"}
    affected = GraphReasoner(graph).affected_subgraph(parameters["p1"], max_depth=4)
    assert parameters["p1"] in affected
    assert parameters["p2"] not in affected


def test_parameter_fusion_normalizes_numeric_strings_and_length_units():
    events = TextAdapter().adapt(run_id="R", entity="E", parameter="p", value="8", unit="mm", raw_text="8")
    events += TextAdapter().adapt(run_id="R", entity="E", parameter="p", value=0.8, unit="cm", raw_text="0.8cm", sequence_start=2)
    fused = GraphReasoner(EngineeringGraph().reduce(events)).fuse_parameters()[0]
    assert fused["status"] == "fused"
    assert fused["value"] == 8
    assert fused["unit"] == "mm"


def test_failure_normalization_keeps_raw_state():
    normalized = GraphReasoner.normalize_failure({"raw_error_code": "BOOLEAN_FAILED", "message": "布尔失败", "status": "failed"})
    assert normalized["signature"] == "cad.boolean_operation_failed"
    assert normalized["raw_error_code"] == "BOOLEAN_FAILED"
    assert normalized["status"] == "failed"
