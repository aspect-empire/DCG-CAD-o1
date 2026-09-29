from gencore.design_state.alignment import AlignmentEngine


def test_exact_template_and_interface_alignment_is_accepted():
    result = AlignmentEngine().align(
        {"name": "框架式基座", "parent": "设备A", "interface": "安装面A"},
        [{"uid": "template:frame", "name": "框架式基座", "parent": "设备A", "interface": "安装面A"}],
    )

    assert result.status == "aligned"
    assert result.target_uid == "template:frame"
    assert result.score_components["name"] == 1.0
    assert set(result.score_components) == {"name", "hierarchy", "geometry", "interface", "context", "conflict"}


def test_close_candidates_are_preserved_as_ambiguous():
    candidates = [
        {"uid": "a", "name": "框架基座", "parent": "设备A"},
        {"uid": "b", "name": "框架式基座", "parent": "设备A"},
    ]

    result = AlignmentEngine(ambiguity_margin=0.1).align(
        {"name": "框架基座", "parent": "设备A"},
        candidates,
    )

    assert result.status == "ambiguous"
    assert result.target_uid is None
    assert set(result.candidate_uids) == {"a", "b"}


def test_low_similarity_is_unresolved_and_candidates_remain_ranked():
    result = AlignmentEngine(accept_threshold=0.8).align(
        {"name": "圆筒设备基座", "parent": "设备A", "interface": "底面"},
        [{"uid": "template:wall", "name": "壁挂支架", "parent": "舱壁", "interface": "侧面"}],
    )

    assert result.status == "unresolved"
    assert result.target_uid is None
    assert result.candidate_uids == ("template:wall",)


def test_conflict_flag_reduces_otherwise_identical_candidate_score():
    engine = AlignmentEngine(ambiguity_margin=0.01)
    result = engine.align(
        {"name": "框架式基座", "parent": "设备A"},
        [
            {"uid": "clean", "name": "框架式基座", "parent": "设备A"},
            {"uid": "conflict", "name": "框架式基座", "parent": "设备A", "conflict": True},
        ],
    )

    assert result.status == "aligned"
    assert result.target_uid == "clean"
    assert result.ranked_scores[0][0] == "clean"
