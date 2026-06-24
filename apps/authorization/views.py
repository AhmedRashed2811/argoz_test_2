"""Authorization views (docs §4.4, §14): manage roles, permission catalog, and
the per-user permission matrix showing role defaults, allows, denies, and the
effective result. Writes go through PermissionManagementService."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import User

from .decorators import crm_permission_required
from .forms import RoleForm, UserOverrideForm
from .models import PermissionDefinition, RoleGroup
from .services import EffectivePermissionResolver, PermissionManagementService


@login_required
@crm_permission_required("authorization.roles.manage")
def role_list(request):
    return render(request, "authorization/role_list.html", {
        "roles": RoleGroup.objects.filter(company=request.company),
    })


@login_required
@crm_permission_required("authorization.roles.manage")
def role_create(request):
    form = RoleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        role = form.save(commit=False)
        role.company = request.company
        role.save()
        messages.success(request, "Role created.")
        return redirect("authorization:role_list")
    return render(request, "form.html", {"title": "New role", "form": form})


@login_required
@crm_permission_required("authorization.permissions.manage")
def permission_catalog(request):
    return render(request, "authorization/permission_catalog.html", {
        "permissions": PermissionDefinition.objects.all().order_by("module", "code"),
    })


@login_required
@crm_permission_required("authorization.roles.manage")
def user_permission_matrix(request, user_id):
    """Show effective result + apply a direct ALLOW/DENY override (docs §4.4)."""
    target = get_object_or_404(User, id=user_id, profile__company=request.company)
    form = UserOverrideForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        PermissionManagementService.set_user_override(
            user=target, permission=d["permission"], effect=d["effect"],
            reason=d["reason"], created_by=request.user,
        )
        messages.success(request, "Override applied.")
        return redirect("authorization:user_matrix", user_id=target.id)
    return render(request, "authorization/user_matrix.html", {
        "target": target,
        "effective": sorted(EffectivePermissionResolver.get_codes(target)),
        "form": form,
    })


@login_required
@crm_permission_required("authorization.roles.manage")
def permission_preview(request, user_id):
    """Simulate what a user can see/do before account activation (docs §4.4).
    Shows all pages they can access and all actions available to them."""
    from apps.authorization.models import PageDefinition

    target = get_object_or_404(User, id=user_id, profile__company=request.company)
    effective_codes = EffectivePermissionResolver.get_codes(target)
    all_perms = PermissionDefinition.objects.filter(
        code__in=effective_codes
    ).order_by("module", "code")
    accessible_pages = PageDefinition.objects.filter(
        code__in={p.code.rsplit(".", 1)[0] for p in all_perms}
    ).order_by("menu_order")
    return render(request, "authorization/permission_preview.html", {
        "target": target,
        "effective_codes": sorted(effective_codes),
        "permissions": all_perms,
        "accessible_pages": accessible_pages,
    })


@login_required
@crm_permission_required("authorization.roles.manage")
def permission_audit(request):
    """Trace who changed permissions/roles, when, and why (docs §4.4)."""
    from apps.audit.models import AuditLog
    from apps.core.constants import AuditAction

    qs = AuditLog.objects.filter(
        company=request.company,
        entity_type__in=["UserPermissionOverride", "UserRole", "RolePermission"],
    ).select_related("actor").order_by("-created_at")
    user_filter = request.GET.get("user_id")
    if user_filter:
        qs = qs.filter(after_json__icontains=user_filter)
    from django.core.paginator import Paginator
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "authorization/permission_audit.html", {"page": page})
