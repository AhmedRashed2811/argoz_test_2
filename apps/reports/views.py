"""Dashboard + reports (docs §14). Permission-scoped read-only summaries."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.authorization.services import RoleService

from .selectors import active_lead_counts, leads_for_user


@login_required
def dashboard_index(request):
    landing = RoleService.default_landing(request.user)
    if landing:
        return redirect(landing)

    return render(request, "reports/welcome.html", {})

