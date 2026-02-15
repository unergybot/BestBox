import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests
from langchain_core.tools import tool

from services.customer_config import get_integration_config


def _oa_webhook_url() -> str:
    cfg = get_integration_config("oa")
    return (
        os.getenv("OA_WEBHOOK_URL")
        or os.getenv("OA_URL")
        or cfg.get("base_url")
        or ""
    ).strip()


def _oa_timeout() -> int:
    return int(os.getenv("OA_TIMEOUT", "5"))


def _not_configured(tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "not_configured",
        "tool": tool_name,
        "message": "OA backend is not configured. Set OA_WEBHOOK_URL or integrations.oa.base_url.",
        "draft": payload,
    }


def _post_to_oa(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    webhook = _oa_webhook_url()
    if not webhook:
        return _not_configured(action, payload)

    response = requests.post(
        webhook,
        json={"action": action, "payload": payload},
        timeout=_oa_timeout(),
    )
    response.raise_for_status()
    body = response.json() if response.content else {}
    if isinstance(body, dict):
        body.setdefault("status", "submitted")
        return body
    return {"status": "submitted", "response": body}

@tool
def draft_email(recipient: str, subject: str, context: str):
    """
    Draft an email based on the context provided.
    """
    draft = {
        "to": recipient,
        "subject": subject,
        "body": f"Dear {recipient},\n\nRegarding: {subject}\n\n{context}\n\nBest regards,\n[Your Name]",
        "status": "draft_created",
        "draft_id": f"OA-DRAFT-{uuid.uuid4().hex[:10]}",
    }
    try:
        result = _post_to_oa("draft_email", draft)
        return {**draft, "integration": result}
    except Exception as exc:
        return {**draft, "integration_error": str(exc)}

@tool
def schedule_meeting(participants: List[str], time: str, topic: str):
    """
    Schedule a team meeting.
    """
    draft_event = {
        "event_id": f"EVT-{uuid.uuid4().hex[:8]}",
        "topic": topic,
        "participants": participants,
        "time": time,
        "location": "Conference Room B / Zoom",
        "status": "pending_submission",
    }
    try:
        result = _post_to_oa("schedule_meeting", draft_event)
        return {**draft_event, "integration": result}
    except Exception as exc:
        return {**draft_event, "integration_error": str(exc)}

@tool
def generate_document(template_type: str, data: dict):
    """
    Generate a formal document from a template.
    Args:
        template_type: e.g., "leave_request", "project_proposal"
        data: Key-value pairs for the template
    """
    doc_payload = {
        "doc_id": f"DOC-{uuid.uuid4().hex[:8]}",
        "type": template_type,
        "content_summary": f"Generated {template_type} with data: {list(data.keys())}",
        "url": f"http://internal-docs/{template_type}/{uuid.uuid4().hex[:8]}.pdf",
        "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z",
    }
    try:
        result = _post_to_oa("generate_document", {"template_type": template_type, "data": data, **doc_payload})
        return {**doc_payload, "integration": result}
    except Exception as exc:
        return {**doc_payload, "integration_error": str(exc)}
