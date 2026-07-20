import asyncio
import json
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pipeline import LogPipeline

app = FastAPI(title="LogGuard AI", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = LogPipeline()
stream_running = False


class CodeAnalysisRequest(BaseModel):
    code: str


class FeedbackRequest(BaseModel):
    alert_id: str
    was_correct: bool
    feedback_text: str = ""


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "logguard-ai", "version": "0.2.0"}


@app.get("/api/metrics/roi")
def get_roi():
    return pipeline.get_roi_metrics()


@app.get("/api/alerts")
def get_alerts():
    return {"alerts": pipeline.alerts[:20]}


@app.get("/api/noise/top")
def get_top_noise():
    return {"patterns": pipeline.get_top_noise()}


@app.get("/api/remediation/pr/{pr_id}")
def get_pr(pr_id: str):
    pr = pipeline.get_pr(pr_id)
    if not pr:
        return {"error": "PR not found", "id": pr_id}
    return pr


@app.post("/api/analyze/code")
def analyze_code(body: CodeAnalysisRequest):
    return pipeline.analyze_code(body.code)


@app.post("/api/stream/start")
def start_stream():
    global stream_running
    stream_running = True
    return {"status": "started"}


@app.post("/api/stream/stop")
def stop_stream():
    global stream_running
    stream_running = False
    return {"status": "stopped"}


@app.get("/api/stream/logs")
async def stream_logs():
    async def event_generator():
        global stream_running
        stream_running = True
        samples = pipeline.get_sample_stream()
        idx = 0

        while stream_running:
            entry = samples[idx % len(samples)]
            if idx >= len(samples) and idx % 7 == 0:
                entry = {
                    **entry,
                    "message": entry["message"].replace("retry", "retry"),
                }

            result = pipeline.process_log(
                entry["message"],
                {
                    "service": entry.get("service"),
                    "level": entry.get("level"),
                    "timestamp": entry.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                },
            )

            payload = {
                "type": "log",
                "data": result,
                "agent_status": {
                    "privacy": "alert" if result["has_pii"] else "active",
                    "noise": "processing",
                    "remediation": "ready" if result.get("remediation_id") else "idle",
                },
            }
            yield f"data: {json.dumps(payload)}\n\n"
            idx += 1
            await asyncio.sleep(0.4)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.post("/api/feedback")
def submit_feedback(body: FeedbackRequest):
    """Log user feedback for model improvement"""
    feedback_entry = pipeline.log_user_feedback(
        body.alert_id, body.was_correct, body.feedback_text
    )
    return {
        "id": feedback_entry["id"],
        "status": "recorded",
        "accuracy": pipeline.get_accuracy_metrics(),
    }


@app.get("/api/metrics/accuracy")
def get_accuracy():
    """Get accuracy metrics from user feedback"""
    return pipeline.get_accuracy_metrics()


@app.get("/api/analytics/trends")
def get_trends():
    """Get trend analysis for alerts and noise"""
    return pipeline.analyze_trends()


@app.get("/api/analytics/root-cause")
def get_root_cause():
    """Get root cause analysis of recent issues"""
    return pipeline.get_root_cause_analysis()


@app.get("/api/metrics/full")
def get_full_metrics():
    """Get comprehensive metrics including ROI, accuracy, and trends"""
    return {
        "roi": pipeline.get_roi_metrics(),
        "accuracy": pipeline.get_accuracy_metrics(),
        "trends": pipeline.analyze_trends(),
        "root_cause": pipeline.get_root_cause_analysis(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
