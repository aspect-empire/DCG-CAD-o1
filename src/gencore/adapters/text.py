from __future__ import annotations

from typing import Any

from ..events import EngineeringEvent, EventSource, canonical_hash


class TextAdapter:
    producer = "text_adapter"

    def adapt(self, *, run_id: str, entity: str, parameter: str, value: Any, unit: str,
              raw_text: str, entity_type: str = "EngineeringEntity", path: str = "inline.txt",
              locator: str = "text:0", sequence_start: int = 1,
              occurred_at: str = "1970-01-01T00:00:00Z") -> list[EngineeringEvent]:
        digest = canonical_hash({"path": path, "raw_text": raw_text})
        source = EventSource(f"artifact:{digest}", path, locator, digest)
        payload = {"entity": entity, "entity_type": entity_type, "parameter": parameter,
                   "value": value, "unit": unit, "raw_text": raw_text}
        return [EngineeringEvent.create(run_id, sequence_start, "parameter.observed", occurred_at,
                                        self.producer, source, payload)]

    ingest = adapt


def adapt_text_assertion(**kwargs: Any) -> list[EngineeringEvent]:
    return TextAdapter().adapt(**kwargs)
