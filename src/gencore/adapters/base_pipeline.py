from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..events import EngineeringEvent, EventSource, canonical_hash


def _pick(row: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return default


def _items(value: Any) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [value]
    return [item for item in value if isinstance(item, Mapping)]


class BasePipelineAdapter:
    producer = "base_pipeline_adapter"
    section_types = {
        "规则应用记录": "rule.applied", "规则执行记录": "rule.applied",
        "工具调用记录": "tool.used", "执行记录": "execution.completed", "执行结果": "execution.completed",
        "校验结果": "validation.completed", "校验报告": "validation.completed",
    }

    def adapt(self, pipeline_result: Mapping[str, Any], *, run_id: str,
              path: str = "pipeline_result.json", sequence_start: int = 1,
              occurred_at: str = "1970-01-01T00:00:00Z") -> list[EngineeringEvent]:
        digest = canonical_hash(pipeline_result)
        artifact_id = f"artifact:{digest}"
        events: list[EngineeringEvent] = []

        def emit(event_type: str, payload: Mapping[str, Any], locator: str) -> EngineeringEvent:
            event = EngineeringEvent.create(run_id, sequence_start + len(events), event_type, occurred_at,
                                            self.producer, EventSource(artifact_id, path, locator, digest), payload)
            events.append(event)
            return event

        for index, row in enumerate(_items(pipeline_result.get("参数逐步生成表"))):
            emit("parameter.observed", {
                "entity": _pick(row, "实体", "所属实体", "对象", default="未指定实体"),
                "entity_type": _pick(row, "实体类型", default="EngineeringEntity"),
                "parameter": _pick(row, "参数名", "参数", "名称"),
                "value": _pick(row, "参数值", "值", "value"), "unit": _pick(row, "单位", "unit", default=""),
                "raw": dict(row),
            }, f"$.参数逐步生成表[{index}]")

        for section, event_type in self.section_types.items():
            for index, row in enumerate(_items(pipeline_result.get(section))):
                locator = f"$.{section}" + (f"[{index}]" if isinstance(pipeline_result.get(section), list) else "")
                status = str(_pick(row, "状态", "结果", "status", default="unknown"))
                payload = {"status": status, "raw": dict(row)}
                if event_type == "rule.applied":
                    payload["rule_id"] = _pick(row, "规则ID", "规则", "规则名", default="unknown")
                elif event_type == "tool.used":
                    payload["tool"] = _pick(row, "工具名", "工具", default="unknown")
                elif event_type == "validation.completed":
                    payload["validation"] = _pick(row, "校验项", "名称", default="validation")
                    payload["passed"] = status.lower() in {"pass", "passed", "success", "成功", "通过", "合格"}
                emit(event_type, payload, locator)
                if event_type == "validation.completed" and not payload["passed"]:
                    emit("failure.observed", {
                        "raw_error_code": _pick(row, "错误码", "错误代码", "error_code", default="VALIDATION_FAILED"),
                        "message": _pick(row, "错误信息", "消息", "message", default=status),
                        "status": "failed", "validation": payload["validation"], "raw": dict(row),
                    }, locator)
        return events

    ingest = adapt


def adapt_base_pipeline(pipeline_result: Mapping[str, Any], **kwargs: Any) -> list[EngineeringEvent]:
    return BasePipelineAdapter().adapt(pipeline_result, **kwargs)
