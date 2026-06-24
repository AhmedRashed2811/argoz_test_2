"""Captures request context for audit (docs §6, §16 RequestMeta.from_request).
Stashes a lightweight RequestMeta on the request; AuditService consumes it.
Full AuditLog model + AuditService land in Phase 4."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RequestMeta:
    ip: str = ""
    user_agent: str = ""
    path: str = ""
    method: str = ""

    @classmethod
    def from_request(cls, request) -> "RequestMeta":
        if request is None:
            return cls()
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")
        return cls(
            ip=ip,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
            path=request.path,
            method=request.method,
        )

    def as_dict(self) -> dict:
        return {
            "ip": self.ip,
            "user_agent": self.user_agent,
            "path": self.path,
            "method": self.method,
        }


class RequestMetaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_meta = RequestMeta.from_request(request)
        return self.get_response(request)
