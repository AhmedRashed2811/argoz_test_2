"""Attaches request.company so views/services share one tenant context
(docs §2.3, §4.5 uses request.company). Thin: resolution lives in the service."""
from .services import CurrentCompanyResolver


class CurrentCompanyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.company = CurrentCompanyResolver.resolve(request)
        return self.get_response(request)
