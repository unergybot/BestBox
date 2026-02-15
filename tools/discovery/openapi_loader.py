from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, create_model


def _http_call(
    method: str,
    url: str,
    auth_header: Optional[str],
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    headers = {"Accept": "application/json"}
    if auth_header:
        headers["Authorization"] = auth_header

    response = requests.request(method=method.upper(), url=url, headers=headers, params=params, json=body, timeout=15)
    response.raise_for_status()
    if not response.content:
        return {"status": "ok"}
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}


def _input_model_for_operation(name: str, operation: Dict[str, Any]) -> type[BaseModel]:
    properties: Dict[str, Any] = {}

    for param in operation.get("parameters", []):
        pname = param.get("name")
        if not pname:
            continue
        required = bool(param.get("required", False))
        ptype = str(param.get("schema", {}).get("type", "string")).lower()
        py_type = int if ptype == "integer" else float if ptype == "number" else bool if ptype == "boolean" else str
        default = ... if required else None
        properties[pname] = (Optional[py_type] if not required else py_type, default)

    return create_model(f"OpenAPIToolInput_{name}", **properties)


def _is_allowed(method: str, path: str, allowlist: List[str]) -> bool:
    if not allowlist:
        return True
    candidate = f"{method.upper()} {path}"
    return any(token.lower() in candidate.lower() for token in allowlist)


def load_tools_from_spec(spec_url: str, allowlist: List[str], auth_header: Optional[str] = None) -> List[StructuredTool]:
    """Parse OpenAPI spec and create one StructuredTool per allowed operation.

    allowlist can include method/path fragments like:
      - "GET /api/resource/Customer"
      - "/api/method/frappe.client.get_list"
    """
    response = requests.get(spec_url, timeout=20)
    response.raise_for_status()
    spec = response.json()

    servers = spec.get("servers", [])
    base_url = servers[0].get("url") if servers else spec_url.rsplit("/", 1)[0]

    tools: List[StructuredTool] = []

    for path, methods in spec.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue

        for method, operation in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(operation, dict):
                continue
            if not _is_allowed(method, path, allowlist):
                continue

            op_id = operation.get("operationId") or f"{method}_{path.strip('/').replace('/', '_').replace('{', '').replace('}', '')}"
            description = operation.get("summary") or operation.get("description") or f"OpenAPI generated tool for {method.upper()} {path}"
            input_model = _input_model_for_operation(op_id, operation)

            def _run_factory(http_method: str, http_path: str):
                def _run(**kwargs: Any) -> Dict[str, Any]:
                    path_params = {k: v for k, v in kwargs.items() if f"{{{k}}}" in http_path and v is not None}
                    request_path = http_path
                    for key, value in path_params.items():
                        request_path = request_path.replace(f"{{{key}}}", str(value))

                    remaining = {k: v for k, v in kwargs.items() if k not in path_params and v is not None}
                    params = remaining if http_method.upper() == "GET" else None
                    body = None if http_method.upper() == "GET" else remaining
                    return _http_call(http_method, f"{base_url}{request_path}", auth_header, params=params, body=body)

                return _run

            tool = StructuredTool.from_function(
                func=_run_factory(method, path),
                name=op_id,
                description=description,
                args_schema=input_model,
            )
            tools.append(tool)

    return tools
