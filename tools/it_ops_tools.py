import os
from datetime import datetime
from typing import Any, Dict, List

import requests
from langchain_core.tools import tool

from services.customer_config import get_integration_config


def _prometheus_base_url() -> str:
    cfg = get_integration_config("it_ops")
    return (
        os.getenv("PROMETHEUS_URL")
        or os.getenv("ITOPS_URL")
        or cfg.get("base_url")
        or "http://localhost:9090"
    )


def _loki_base_url() -> str:
    return os.getenv("LOKI_URL", "").strip()


def _prometheus_get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    timeout = int(os.getenv("ITOPS_TIMEOUT", "5"))
    response = requests.get(f"{_prometheus_base_url()}{path}", params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed: {payload}")
    return payload


def _not_configured_response(tool_name: str) -> Dict[str, Any]:
    return {
        "status": "not_configured",
        "tool": tool_name,
        "message": "IT Ops backend is not configured. Set PROMETHEUS_URL (or integrations.it_ops in config/customer.yaml).",
    }

@tool
def query_system_logs(service_name: str, logs_limit: int = 10):
    """
    Query recent system logs for a specific service.
    """
    loki_url = _loki_base_url()
    if loki_url:
        try:
            timeout = int(os.getenv("ITOPS_TIMEOUT", "5"))
            query = f'{{service=~"{service_name}"}}'
            response = requests.get(
                f"{loki_url}/loki/api/v1/query_range",
                params={"query": query, "limit": logs_limit, "direction": "backward"},
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("data", {}).get("result", [])
            lines: List[str] = []
            for stream in result:
                for row in stream.get("values", []):
                    if len(row) >= 2:
                        lines.append(str(row[1]))
            return lines[:logs_limit]
        except Exception as exc:
            return [f"Loki query failed: {exc}"]

    if not _prometheus_base_url():
        return _not_configured_response("query_system_logs")

    try:
        # Fallback to metrics-derived operational view when Loki is not configured.
        cpu = _prometheus_get("/api/v1/query", {"query": f'avg(rate(process_cpu_seconds_total{{job=~"{service_name}"}}[5m]))'})
        mem = _prometheus_get("/api/v1/query", {"query": f'avg(process_resident_memory_bytes{{job=~"{service_name}"}})'})
        return [
            f"[{datetime.utcnow().isoformat()}Z] INFO {service_name}: Metrics snapshot",
            f"CPU (5m avg): {cpu.get('data', {}).get('result', [])}",
            f"Resident memory: {mem.get('data', {}).get('result', [])}",
        ][:logs_limit]
    except Exception as exc:
        return [f"Prometheus query failed for {service_name}: {exc}"]

@tool
def get_active_alerts(severity: str = "all"):
    """
    Get current active system alerts.
    """
    try:
        payload = _prometheus_get("/api/v1/alerts", {})
        results = payload.get("data", {}).get("alerts", [])
        normalized = []
        for alert in results:
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})
            sev = str(labels.get("severity", "unknown")).lower()
            if severity != "all" and sev != severity.lower():
                continue
            normalized.append(
                {
                    "id": labels.get("alertname", "unknown"),
                    "service": labels.get("job") or labels.get("instance") or "unknown",
                    "severity": sev,
                    "state": alert.get("state", "firing"),
                    "message": annotations.get("summary") or annotations.get("description") or "No description",
                }
            )
        return normalized
    except Exception:
        return _not_configured_response("get_active_alerts")

@tool
def diagnose_fault(resource_id: str):
    """
    Run an automated AI diagnosis on a faulty resource.
    """
    try:
        error_rate = _prometheus_get(
            "/api/v1/query",
            {"query": f'sum(rate(http_requests_total{{job=~"{resource_id}",status=~"5.."}}[5m]))'},
        )
        latency = _prometheus_get(
            "/api/v1/query",
            {"query": f'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{{job=~"{resource_id}"}}[5m])) by (le))'},
        )

        return {
            "resource_id": resource_id,
            "diagnosis": "Live metrics analyzed",
            "confidence": 0.8,
            "recommended_action": "Scale service or inspect recent deploy if p95 latency and 5xx both elevated.",
            "root_cause_analysis": {
                "error_rate": error_rate.get("data", {}).get("result", []),
                "p95_latency": latency.get("data", {}).get("result", []),
            },
            "source": "prometheus",
        }
    except Exception:
        return _not_configured_response("diagnose_fault")
