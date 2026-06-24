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
from .services import EffectivePermissionResolver, PermissionManagementService, RoleService


@login_required
@crm_permission_required("authorization.roles.manage")
def role_list(request):
    roles = RoleService.get_roles_for_company(request.company)
    return render(request, "authorization/role_list.html", {"roles": roles})


@login_required
@crm_permission_required("authorization.roles.manage")
def role_create(request):
    form = RoleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        RoleService.create_role(
            company=request.company,
            code=form.cleaned_data["code"],
            name=form.cleaned_data["name"],
            description=form.cleaned_data["description"],
            is_active=form.cleaned_data["is_active"],
            permission_ids=request.POST.getlist("permissions"),
            actor=request.user,
            request_meta=request.request_meta,
        )
        messages.success(request, "Role created.")
        return redirect("authorization:role_list")
    
    context = {
        "form": form,
        "permissions": PermissionManagementService.get_active_permissions(),
        "selected_permission_ids": set(),
    }
    return render(request, "authorization/role_form.html", context)


@login_required
@crm_permission_required("authorization.roles.manage")
def role_edit(request, role_id):
    role = get_object_or_404(RoleGroup, id=role_id, company=request.company)
    form = RoleForm(request.POST or None, instance=role)
    if request.method == "POST" and form.is_valid():
        RoleService.update_role(
            role=role,
            code=form.cleaned_data["code"],
            name=form.cleaned_data["name"],
            description=form.cleaned_data["description"],
            is_active=form.cleaned_data["is_active"],
            permission_ids=request.POST.getlist("permissions"),
            actor=request.user,
            request_meta=request.request_meta,
        )
        messages.success(request, "Role updated.")
        return redirect("authorization:role_list")
    
    current_permission_ids = set(
        str(pid) for pid in role.permissions.values_list("permission_id", flat=True)
    )
    context = {
        "form": form,
        "role_instance": role,
        "is_edit_mode": True,
        "permissions": PermissionManagementService.get_active_permissions(),
        "selected_permission_ids": current_permission_ids,
    }
    return render(request, "authorization/role_form.html", context)


@login_required
@crm_permission_required("authorization.roles.manage")
def role_toggle(request, role_id):
    role = get_object_or_404(RoleGroup, id=role_id, company=request.company)
    try:
        is_active = RoleService.toggle_role(role=role, actor=request.user, request_meta=request.request_meta)
        messages.success(request, f"Role {'activated' if is_active else 'deactivated'}.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("authorization:role_list")


@login_required
@crm_permission_required("authorization.permissions.manage")
def permission_catalog(request):
    return render(request, "authorization/permission_catalog.html", {
        "permissions": PermissionManagementService.get_permission_catalog(),
    })


@login_required
@crm_permission_required("authorization.roles.manage")
def user_permission_matrix(request, user_id):
    """Show effective result + apply direct ALLOW/DENY overrides (docs §4.4)."""
    target = get_object_or_404(User, id=user_id, profile__company=request.company)
    
    if request.method == "POST":
        permission_codes = request.POST.getlist("permissions")
        PermissionManagementService.update_user_overrides(
            user=target,
            permission_codes=permission_codes,
            created_by=request.user,
            request_meta=request.request_meta,
        )
        messages.success(request, "Permission overrides updated successfully.")
        return redirect("authorization:user_matrix", user_id=target.id)
        
    from apps.accounts.services import UserService
    from apps.authorization.services import EffectivePermissionResolver
    
    context = UserService.get_user_creation_context(company=request.company)
    context["target"] = target
    context["user_active_permissions"] = EffectivePermissionResolver.get_codes(target)
    return render(request, "authorization/user_matrix.html", context)


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
