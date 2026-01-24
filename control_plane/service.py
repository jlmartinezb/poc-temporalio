import asyncio
import json
import os
import time
from typing import Any, Dict, List

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from temporalio.client import Client

app = FastAPI()

CHECK_INTERVAL_SEC = float(os.environ.get("CONTROL_PLANE_INTERVAL_SEC", "10"))
SSE_INTERVAL_SEC = float(os.environ.get("CONTROL_PLANE_SSE_INTERVAL_SEC", "1"))
WORKER_TTL_SEC = float(os.environ.get("WORKER_TTL_SEC", "20"))
ALERT_HISTORY_MAX = int(os.environ.get("ALERT_HISTORY_MAX", "200"))
TEMPORAL_SERVER = os.environ.get("TEMPORAL_SERVER", "localhost:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8000")

_state: Dict[str, Any] = {
    "temporal": {"status": "unknown", "checked_at": None},
    "gateway": {"status": "unknown", "checked_at": None},
    "workers": {"status": "unknown", "checked_at": None, "entries": {}},
    "last_run_at": None,
    "alerts": [],
    "component_status": {},
}

class WorkerHeartbeat(BaseModel):
    task_queue: str
    worker_id: str
    version: str | None = None
    metadata: Dict[str, Any] | None = None


def _now() -> float:
    return time.time()


def _record_alert(component: str, status: str, message: str) -> None:
    alert = {
        "id": f"{component}-{int(_now())}",
        "component": component,
        "status": status,
        "message": message,
        "created_at": _now(),
    }
    _state["alerts"].append(alert)
    if len(_state["alerts"]) > ALERT_HISTORY_MAX:
        _state["alerts"] = _state["alerts"][-ALERT_HISTORY_MAX:]


def _update_component_status(component: str, status: str, message: str) -> None:
    previous = _state["component_status"].get(component)
    if previous != status:
        _record_alert(component, status, message)
        _state["component_status"][component] = status


def _build_snapshot() -> Dict[str, Any]:
    temporal = _state["temporal"]
    gateway = _state["gateway"]
    workers = _state["workers"]
    temporal_ok = temporal.get("status") == "ok"
    gateway_ok = gateway.get("status") == "ok"
    workers_ok = workers.get("status") == "ok"
    overall = "ok" if temporal_ok and gateway_ok and workers_ok else "degraded"
    return {
        "overall": overall,
        "components": {
            "temporal": temporal,
            "gateway": gateway,
            "workers": workers,
        },
        "alerts": list(_state["alerts"][-10:]),
        "last_run_at": _state["last_run_at"],
    }


async def check_temporal() -> Dict[str, Any]:
    started = _now()
    try:
        client = await Client.connect(TEMPORAL_SERVER)
        if hasattr(client, "describe_namespace"):
            await client.describe_namespace(TEMPORAL_NAMESPACE)
        else:
            service = client.workflow_service
            try:
                await service.describe_namespace(namespace=TEMPORAL_NAMESPACE)
            except TypeError:
                from temporalio.api.workflowservice.v1 import DescribeNamespaceRequest

                await service.describe_namespace(
                    DescribeNamespaceRequest(namespace=TEMPORAL_NAMESPACE)
                )
        latency_ms = int((_now() - started) * 1000)
        return {
            "status": "ok",
            "server": TEMPORAL_SERVER,
            "namespace": TEMPORAL_NAMESPACE,
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        return {
            "status": "error",
            "server": TEMPORAL_SERVER,
            "namespace": TEMPORAL_NAMESPACE,
            "error": str(exc),
        }


async def check_gateway() -> Dict[str, Any]:
    started = _now()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{GATEWAY_URL}/")
        latency_ms = int((_now() - started) * 1000)
        return {
            "status": "ok" if resp.status_code < 500 else "error",
            "gateway_url": GATEWAY_URL,
            "http_status": resp.status_code,
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        return {
            "status": "error",
            "gateway_url": GATEWAY_URL,
            "error": str(exc),
        }


def _evaluate_workers() -> Dict[str, Any]:
    entries = _state["workers"]["entries"]
    now = _now()
    degraded = False
    evaluated = {}
    if not entries:
        return {"status": "unknown", "entries": {}}
    for worker_key, details in entries.items():
        last_seen = details.get("last_seen")
        age = None if last_seen is None else int(now - last_seen)
        is_stale = age is not None and age > WORKER_TTL_SEC
        evaluated[worker_key] = {
            **details,
            "age_sec": age,
            "stale": is_stale,
        }
        if is_stale:
            degraded = True

    status = "degraded" if degraded else "ok"
    return {"status": status, "entries": evaluated}


async def collector_loop() -> None:
    while True:
        temporal_result, gateway_result = await asyncio.gather(
            check_temporal(), check_gateway()
        )
        _state["temporal"] = {**temporal_result, "checked_at": _now()}
        _state["gateway"] = {**gateway_result, "checked_at": _now()}

        worker_eval = _evaluate_workers()
        _state["workers"] = {
            "status": worker_eval["status"],
            "checked_at": _now(),
            "entries": worker_eval["entries"],
        }

        _update_component_status(
            "temporal",
            temporal_result["status"],
            f"Temporal status: {temporal_result['status']}",
        )
        _update_component_status(
            "gateway",
            gateway_result["status"],
            f"Gateway status: {gateway_result['status']}",
        )
        _update_component_status(
            "workers",
            worker_eval["status"],
            f"Workers status: {worker_eval['status']}",
        )

        _state["last_run_at"] = _now()
        await asyncio.sleep(CHECK_INTERVAL_SEC)


@app.on_event("startup")
async def startup() -> None:
    app.state.collector_task = asyncio.create_task(collector_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    task = getattr(app.state, "collector_task", None)
    if task:
        task.cancel()


@app.get("/health")
async def health() -> Dict[str, Any]:
    snapshot = _build_snapshot()
    return {
        "status": snapshot["overall"],
        "components": snapshot["components"],
        "last_run_at": snapshot["last_run_at"],
    }


@app.get("/health/temporal")
async def health_temporal() -> Dict[str, Any]:
    return _state["temporal"]


@app.get("/health/gateway")
async def health_gateway() -> Dict[str, Any]:
    return _state["gateway"]


@app.get("/health/workers")
async def health_workers() -> Dict[str, Any]:
    return _state["workers"]


@app.post("/workers/heartbeat")
async def workers_heartbeat(payload: WorkerHeartbeat) -> Dict[str, Any]:
    key = f"{payload.task_queue}:{payload.worker_id}"
    _state["workers"]["entries"][key] = {
        "task_queue": payload.task_queue,
        "worker_id": payload.worker_id,
        "version": payload.version,
        "metadata": payload.metadata or {},
        "last_seen": _now(),
    }
    return {"status": "ok"}


@app.get("/alerts/history")
async def alerts_history() -> Dict[str, Any]:
    return {"alerts": list(_state["alerts"])}


@app.get("/events")
async def events() -> StreamingResponse:
    async def event_stream():
        while True:
            payload = _build_snapshot()
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(SSE_INTERVAL_SEC)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    components = _state["component_status"]
    alerts = _state["alerts"][-10:]
    workers = _state["workers"].get("entries", {})
    overall = "ok"
    if any(status in ("error", "degraded") for status in components.values()):
        overall = "degraded"
    html = [
        "<html><head><title>Control Plane</title>",
        "<style>",
        "body{font-family:Arial, sans-serif;background:#f6f6f6;color:#111;padding:20px}",
        ".card{background:#fff;padding:16px;margin:10px 0;border-radius:8px}",
        ".ok{color:#0a7b2c}.degraded{color:#b45309}.error{color:#b91c1c}.unknown{color:#6b7280}",
        ".badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px}",
        ".badge.ok{background:#e7f7ee;color:#0a7b2c}",
        ".badge.degraded{background:#fff4e5;color:#b45309}",
        ".badge.error{background:#fdecea;color:#b91c1c}",
        ".badge.unknown{background:#f3f4f6;color:#6b7280}",
        ".charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}",
        "canvas{width:100%;height:80px;border:1px solid #eee;border-radius:6px}",
        "</style></head><body>",
        "<h1>Control Plane</h1>",
        "<div class='card'><strong>Overall:</strong> "
        "<span id='overall-status' class='degraded'>loading</span> "
        "<span id='conn-status' class='badge unknown'>connecting</span>"
        "</div>",
        "<div class='card'><h2>Components</h2>",
        "<div><strong>temporal</strong>: <span id='temporal-status'>loading</span></div>",
        "<div><strong>gateway</strong>: <span id='gateway-status'>loading</span></div>",
        "<div><strong>workers</strong>: <span id='workers-status'>loading</span></div>",
    ]
    html.append("</div>")
    html.append(
        "<div class='card'><h2>Latency (ms)</h2>"
        "<div class='charts'>"
        "<div><div>Temporal</div><canvas id='chart-temporal' width='300' height='80'></canvas></div>"
        "<div><div>Gateway</div><canvas id='chart-gateway' width='300' height='80'></canvas></div>"
        "</div></div>"
    )
    html.append("<div class='card'><h2>Workers</h2><div id='workers-list'>loading</div></div>")
    html.append("<div class='card'><h2>Alerts</h2><div id='alerts-list'>loading</div></div>")
    html.append(
        "<script>"
        "const statusClass = (v) => ['ok','degraded','error','unknown'].includes(v) ? v : 'degraded';"
        "const setStatus = (id, v) => {"
        "  const el = document.getElementById(id);"
        "  if (!el) return;"
        "  el.className = statusClass(v);"
        "  el.textContent = v || 'unknown';"
        "};"
        "const setBadge = (id, v, label) => {"
        "  const el = document.getElementById(id);"
        "  if (!el) return;"
        "  el.className = `badge ${statusClass(v)}`;"
        "  el.textContent = label || v;"
        "};"
        "const renderWorkers = (entries) => {"
        "  const el = document.getElementById('workers-list');"
        "  if (!el) return;"
        "  const keys = entries ? Object.keys(entries) : [];"
        "  if (!keys.length) { el.textContent = 'No worker heartbeats'; return; }"
        "  el.innerHTML = keys.map((key) => {"
        "    const info = entries[key] || {};"
        "    const age = info.age_sec === null || info.age_sec === undefined ? '?' : info.age_sec;"
        "    const stale = info.stale ? 'stale' : 'ok';"
        "    const css = info.stale ? 'degraded' : 'ok';"
        "    return `<div><strong>${key}</strong> age=${age}s <span class='${css}'>${stale}</span></div>`;"
        "  }).join('');"
        "};"
        "const renderAlerts = (alerts) => {"
        "  const el = document.getElementById('alerts-list');"
        "  if (!el) return;"
        "  if (!alerts || !alerts.length) { el.textContent = 'No alerts'; return; }"
        "  el.innerHTML = alerts.map((a) => {"
        "    const css = statusClass(a.status || 'degraded');"
        "    return `<div><strong>${a.component}</strong> <span class='${css}'>${a.status}</span> ${a.message}</div>`;"
        "  }).join('');"
        "};"
        "const series = { temporal: [], gateway: [] };"
        "const maxPoints = 60;"
        "const pushPoint = (arr, val) => {"
        "  arr.push(val);"
        "  if (arr.length > maxPoints) arr.shift();"
        "};"
        "const drawChart = (canvasId, data, color) => {"
        "  const canvas = document.getElementById(canvasId);"
        "  if (!canvas) return;"
        "  const ctx = canvas.getContext('2d');"
        "  const w = canvas.width, h = canvas.height;"
        "  ctx.clearRect(0, 0, w, h);"
        "  if (!data.length) return;"
        "  const max = Math.max(...data, 1);"
        "  ctx.strokeStyle = color;"
        "  ctx.lineWidth = 2;"
        "  ctx.beginPath();"
        "  data.forEach((v, i) => {"
        "    const x = (i / (maxPoints - 1)) * w;"
        "    const y = h - (v / max) * (h - 6) - 3;"
        "    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);"
        "  });"
        "  ctx.stroke();"
        "};"
        "let source = null;"
        "let retry = 1000;"
        "const connect = () => {"
        "  if (source) source.close();"
        "  source = new EventSource('/events');"
        "  setBadge('conn-status', 'unknown', 'connecting');"
        "  source.onopen = () => {"
        "    retry = 1000;"
        "    setBadge('conn-status', 'ok', 'live');"
        "  };"
        "  source.onmessage = (evt) => {"
        "    const payload = JSON.parse(evt.data);"
        "    setStatus('overall-status', payload.overall);"
        "    setStatus('temporal-status', payload.components.temporal.status);"
        "    setStatus('gateway-status', payload.components.gateway.status);"
        "    setStatus('workers-status', payload.components.workers.status);"
        "    renderWorkers(payload.components.workers.entries);"
        "    renderAlerts(payload.alerts);"
        "    if (payload.components.temporal.latency_ms !== undefined) {"
        "      pushPoint(series.temporal, payload.components.temporal.latency_ms);"
        "      drawChart('chart-temporal', series.temporal, '#0a7b2c');"
        "    }"
        "    if (payload.components.gateway.latency_ms !== undefined) {"
        "      pushPoint(series.gateway, payload.components.gateway.latency_ms);"
        "      drawChart('chart-gateway', series.gateway, '#2563eb');"
        "    }"
        "  };"
        "  source.onerror = () => {"
        "    setBadge('conn-status', 'degraded', 'reconnecting');"
        "    source.close();"
        "    setTimeout(connect, retry);"
        "    retry = Math.min(retry * 2, 10000);"
        "  };"
        "};"
        "connect();"
        "</script></body></html>"
    )
    return HTMLResponse("\n".join(html))
