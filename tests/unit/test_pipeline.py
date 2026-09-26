import pytest
import time
from app.core.models import PipelineRequest, PipelineTrace
from app.multimodal.router import IntelligenceRouter, ContextRequirements

def test_pipeline_request_id():
    req1 = PipelineRequest(text="hello", intent="CONVERSATION")
    req2 = PipelineRequest(text="world", intent="CONVERSATION")
    assert req1.request_id != req2.request_id
    assert req1.request_id.startswith("REQ-")

def test_intelligence_router():
    router = IntelligenceRouter()
    
    # Audio only
    reqs = router.route("QUESTION", "what is binary search", [])
    assert reqs.screen is False
    assert reqs.coding is False
    
    # Screen required
    reqs = router.route("QUESTION", "what is wrong with this code", [])
    assert reqs.screen is True
    assert reqs.ocr is True
    assert reqs.coding is True
    
    # Command
    reqs = router.route("COMMAND", "reset session", [])
    assert reqs.screen is False
    assert reqs.session is False

def test_trace_total():
    trace = PipelineTrace(stt_ms=10, routing_ms=5, capture_ms=100, ocr_ms=500, analysis_ms=10, llm_ms=1000, overlay_ms=5)
    assert trace.total_ms == 1630
