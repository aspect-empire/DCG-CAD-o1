from gencore.adapters import BasePipelineAdapter, CadReportAdapter, TextAdapter


def test_text_adapter_preserves_raw_evidence():
    events = TextAdapter().adapt(run_id="EX-01", entity="肘板A", parameter="孔边距", value=8, unit="mm", raw_text="肘板A孔边距为8 mm", path="note.txt")
    assert events[0].payload["raw_text"] == "肘板A孔边距为8 mm"
    assert events[0].source.locator == "text:0"


def test_base_pipeline_ingests_chinese_fields_and_failed_validation():
    result = {
        "参数逐步生成表": [{"实体": "肘板A", "参数名": "孔边距", "参数值": 8, "单位": "mm"}],
        "规则应用记录": [{"规则ID": "R-clearance", "结果": "通过"}],
        "工具调用记录": [{"工具名": "base_solver", "状态": "成功"}],
        "执行结果": {"状态": "完成"},
        "校验结果": [{"校验项": "孔边距", "状态": "失败", "错误码": "EDGE_TOO_SMALL"}],
    }
    events = BasePipelineAdapter().adapt(result, run_id="EX-01", path="pipeline_result.json")
    assert {e.event_type for e in events} >= {"parameter.observed", "rule.applied", "tool.used", "execution.completed", "validation.completed", "failure.observed"}
    failure = next(e for e in events if e.event_type == "failure.observed")
    assert failure.payload["raw_error_code"] == "EDGE_TOO_SMALL"
    assert "校验结果" in failure.source.locator


def test_cad_degraded_fallback_never_becomes_full_success():
    report = {"requested_mode": "swept_cut", "actual_mode": "visual_curve", "status": "degraded_success", "failure": {"code": "BOOLEAN_FAILED"}, "fallback": {"mode": "visual_curve"}, "artifact": {"path": "result.CATPart"}, "validation": {"passed": True}}
    events = CadReportAdapter().adapt(report, run_id="EX-02", path="cad_report.json")
    execution = next(e for e in events if e.event_type == "execution.completed")
    assert execution.payload == {"requested_mode": "swept_cut", "actual_mode": "visual_curve", "status": "degraded_success"}
    assert "full_success" not in [e.payload.get("status") for e in events]
    assert {"failure.observed", "fallback.activated", "artifact.produced", "validation.completed"} <= {e.event_type for e in events}
