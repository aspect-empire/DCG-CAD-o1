from gencore.adapters import TextAdapter
from gencore.graph import EngineeringGraph


def test_stable_ids_idempotent_reduction_and_hash():
    event = TextAdapter().adapt(run_id="EX-01", entity="肘板A", parameter="孔边距", value=8, unit="mm", raw_text="孔边距8mm")[0]
    graph = EngineeringGraph()
    graph.reduce([event])
    first = graph.graph_hash()
    graph.reduce([event])
    assert graph.graph_hash() == first
    parameters = [(uid, data) for uid, data in graph.graph.nodes(data=True) if data["node_type"] == "Parameter"]
    assert len(parameters) == 1
    assert parameters[0][0].startswith("node:")
    assert all("edge_uid" in data and data["origin"] == "observed" for *_, data in graph.graph.edges(data=True))


def test_history_is_closed_not_deleted():
    graph = EngineeringGraph()
    first = TextAdapter().adapt(run_id="R", entity="E", parameter="p", value=8, unit="mm", raw_text="8")[0]
    graph.reduce([first])
    uid = next(uid for uid, d in graph.graph.nodes(data=True) if d["node_type"] == "Parameter")
    graph.deactivate_node(uid, "evt:replacement")
    assert graph.graph.nodes[uid]["active"] is False
    assert graph.graph.nodes[uid]["valid_to_event"] == "evt:replacement"


def test_reduction_hash_is_independent_of_input_event_order():
    first, second = TextAdapter().adapt(
        run_id="order", entity="E", parameter="thickness", value=8, unit="mm", raw_text="8"
    ) + TextAdapter().adapt(
        run_id="order", entity="E", parameter="thickness", value=8, unit="mm", raw_text="8", sequence_start=2
    )
    forward = EngineeringGraph().reduce([first, second])
    reverse = EngineeringGraph().reduce([second, first])
    assert forward.graph_hash() == reverse.graph_hash()
