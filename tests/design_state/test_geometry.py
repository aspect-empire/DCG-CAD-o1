import pytest

from gencore.design_state.geometry import GeometryLevel, GeometryReference, ReferenceResolver


def reference(uri="catia://Part1/Face.12"):
    return GeometryReference(
        GeometryLevel.BOUNDARY,
        "mounting_face",
        uri,
        (0.0, 0.0, 1.0, 12000.0),
        ("Pad.1",),
        0.1,
    )


def candidate(uri, *, role="mounting_face", area=12000.02, neighbours=("Pad.1",)):
    return {
        "uri": uri,
        "role": role,
        "signature": (0.0, 0.0, 1.0, area),
        "neighbours": neighbours,
    }


def test_reference_relocates_from_semantics_signature_and_neighbourhood():
    result = ReferenceResolver().resolve(reference(), [candidate("catia://Part1/Face.18")])

    assert result.status == "relocated"
    assert result.resolved_uri == "catia://Part1/Face.18"


@pytest.mark.parametrize(
    "candidates,status",
    [
        ([candidate("catia://Part1/Face.12")], "stable"),
        ([candidate("catia://Part1/Face.18"), candidate("catia://Part1/Face.19")], "ambiguous"),
        ([candidate("catia://Part1/Face.18", role="free_edge")], "lost"),
    ],
)
def test_reference_resolution_states(candidates, status):
    assert ReferenceResolver().resolve(reference(), candidates).status == status


def test_persistent_reference_disagreement_with_semantic_relocation_is_conflicted():
    candidates = [
        candidate("catia://Part1/Face.12", role="free_edge"),
        candidate("catia://Part1/Face.18"),
    ]

    result = ReferenceResolver().resolve(reference(), candidates)

    assert result.status == "conflicted"
    assert result.resolved_uri is None
    assert result.candidate_uris == ("catia://Part1/Face.12", "catia://Part1/Face.18")


def test_geometry_reference_requires_nonnegative_tolerance():
    with pytest.raises(ValueError, match="tolerance"):
        GeometryReference(GeometryLevel.KEYPOINT, "hole_center", "catia://Point.1", (0.0, 0.0, 0.0), (), -0.1)

