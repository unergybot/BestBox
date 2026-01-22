from langchain_core.tools import tool
from typing import List

@tool
def draft_email(recipient: str, subject: str, context: str):
    """
    Draft an email based on the context provided.
    """
    return {
        "to": recipient,
        "subject": subject,
        "body": f"Dear {recipient},\n\nRegarding: {subject}\n\n{context}\n\nBest regards,\n[Your Name]",
        "status": "draft_created"
    }

@tool
def schedule_meeting(participants: List[str], time: str, topic: str):
    """
    Schedule a team meeting.
    """
    return {
        "event_id": "EVT-772",
        "topic": topic,
        "participants": participants,
        "time": time,
        "location": "Conference Room B / Zoom",
        "status": "invitations_sent"
    }

@tool
def generate_document(template_type: str, data: dict):
    """
    Generate a formal document from a template.
    Args:
        template_type: e.g., "leave_request", "project_proposal"
        data: Key-value pairs for the template
    """
    return {
        "doc_id": "DOC-8921",
        "type": template_type,
        "content_summary": f"Generated {template_type} with data: {list(data.keys())}",
        "url": f"http://internal-docs/{template_type}/DOC-8921.pdf"
    }
