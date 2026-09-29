from gencore.design_state.dependencies import (
    DependencyEdge,
    affected_closure,
    affected_subgraph,
)


def test_load_change_only_invalidates_downstream_nodes():
    dependencies = {
        "load": {"band"},
        "band": {"panel_t", "web_t"},
        "web_t": {"load"},
        "unrelated": {"paint"},
    }

    assert affected_closure(dependencies, {"load"}) == {"load", "band", "panel_t", "web_t"}


def test_unknown_start_is_still_reported_as_changed():
    assert affected_closure({}, {"new_requirement"}) == {"new_requirement"}


def test_typed_traversal_obeys_relation_depth_and_stable_path_order():
    edges = (
        DependencyEdge("constraint:new", "parameter:offset", "constrains", 1.0),
        DependencyEdge("parameter:offset", "feature:hole", "generates", 1.0),
        DependencyEdge("feature:hole", "feature:paint", "adjacent", 0.1),
    )

    result = affected_subgraph(
        edges,
        starts={"constraint:new"},
        allowed_relations={"constrains", "generates"},
        max_depth=3,
    )

    assert result.node_uids == (
        "constraint:new",
        "feature:hole",
        "parameter:offset",
    )
    assert tuple(path.relations for path in result.paths) == (
        ("constrains",),
        ("constrains", "generates"),
    )


def test_protected_verified_node_is_not_invalidated_or_traversed():
    edges = (
        DependencyEdge("constraint:new", "parameter:offset", "constrains", 1.0),
        DependencyEdge("parameter:offset", "feature:verified", "generates", 1.0),
        DependencyEdge("feature:verified", "feature:downstream", "generates", 1.0),
    )

    result = affected_subgraph(
        edges,
        starts={"constraint:new"},
        allowed_relations={"constrains", "generates"},
        max_depth=3,
        protected={"feature:verified"},
    )

    assert result.node_uids == ("constraint:new", "parameter:offset")
    assert result.protected_boundaries == ("feature:verified",)
