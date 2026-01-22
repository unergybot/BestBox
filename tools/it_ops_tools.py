from langchain_core.tools import tool

@tool
def query_system_logs(service_name: str, logs_limit: int = 10):
    """
    Query recent system logs for a specific service.
    """
    return [
        f"[2026-01-23 10:00:01] INFO {service_name}: Health check passed",
        f"[2026-01-23 10:05:23] WARN {service_name}: High memory usage (85%)",
        f"[2026-01-23 10:15:00] ERROR {service_name}: Connection timeout to DB-01",
        f"[2026-01-23 10:15:05] INFO {service_name}: Retrying connection...",
    ][-logs_limit:]

@tool
def get_active_alerts(severity: str = "all"):
    """
    Get current active system alerts.
    """
    alerts = [
        {"id": "ALT-001", "service": "db-prod-primary", "severity": "critical", "message": "High CPU utilization (98%)"},
        {"id": "ALT-002", "service": "api-gateway", "severity": "warning", "message": "Increased latency p99 > 500ms"},
        {"id": "ALT-003", "service": "redis-cache", "severity": "info", "message": "Backup completed successfully"}
    ]
    
    if severity != "all":
        return [a for a in alerts if a["severity"] == severity]
    return alerts

@tool
def diagnose_fault(resource_id: str):
    """
    Run an automated AI diagnosis on a faulty resource.
    """
    return {
        "resource_id": resource_id,
        "diagnosis": "Memory leak detected in worker process",
        "confidence": 0.95,
        "recommended_action": "Restart worker service and check memory limit configuration",
        "root_cause_analysis": "Trace logs show unreleased buffer allocation loop in processing module."
    }
