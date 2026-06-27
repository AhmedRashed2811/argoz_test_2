"""Authorization views (docs §4.4, §14): manage roles, permission catalog, and
the per-user permission matrix showing role defaults, allows, denies, and the
effective result. Writes go through PermissionManagementService."""
from __future__ import annotations

from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse

from apps.accounts.models import User
from apps.core.exceptions import PermissionDenied

from .decorators import crm_permission_required
from .forms import RoleForm, UserOverrideForm
from .models import PermissionDefinition, RoleGroup
from .services import EffectivePermissionResolver, PermissionManagementService, RoleService


@login_required
@crm_permission_required("authorization.roles.manage")
def role_list(request):
    return render(request, "authorization/role_list.html")


@login_required
@crm_permission_required("authorization.roles.manage")
def role_create(request):
    context = {
        "permissions": PermissionManagementService.get_active_permissions(),
        "is_edit_mode": False,
        "selected_permission_ids": [],
        "perms_locked": False,
    }
    return render(request, "authorization/role_form.html", context)


@login_required
@crm_permission_required("authorization.roles.manage")
def role_edit(request, role_id):
    role = get_object_or_404(RoleGroup, id=role_id, company=request.company)
    current_permission_ids = list(
        str(pid) for pid in role.permissions.values_list("permission_id", flat=True)
    )
    context = {
        "role_instance": role,
        "is_edit_mode": True,
        "permissions": PermissionManagementService.get_active_permissions(),
        "selected_permission_ids": current_permission_ids,
        # System-default bundles stay locked unless the editor is a Director/superuser.
        "perms_locked": role.is_system_default and not RoleService.is_director(request.user),
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
@crm_permission_required("authorization.roles.manage")
def role_api_list(request):
    roles = RoleService.get_roles_for_company(request.company)
    data = []
    for r in roles:
        data.append({
            "id": str(r.id),
            "name": r.name,
            "code": r.code,
            "description": r.description or "",
            "is_system_default": r.is_system_default,
            "member_count": getattr(r, "member_count", 0),
            "is_active": r.is_active,
        })
    return JsonResponse({"roles": data})


@login_required
@crm_permission_required("authorization.roles.manage")
@require_POST
def role_api_create(request):
    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    form = RoleForm(data)
    if form.is_valid():
        RoleService.create_role(
            company=request.company,
            code=form.cleaned_data["code"],
            name=form.cleaned_data["name"],
            description=form.cleaned_data["description"],
            is_active=form.cleaned_data["is_active"],
            permission_ids=data.get("permissions", []),
            actor=request.user,
            request_meta=request.request_meta,
        )
        return JsonResponse({"ok": True})
    else:
        errors = {field: [str(e) for e in err_list] for field, err_list in form.errors.items()}
        return JsonResponse({"errors": errors}, status=400)


@login_required
@crm_permission_required("authorization.roles.manage")
@require_POST
def role_api_edit(request, role_id):
    import json
    role = get_object_or_404(RoleGroup, id=role_id, company=request.company)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    form = RoleForm(data, instance=role)
    if form.is_valid():
        try:
            RoleService.update_role(
                role=role,
                code=form.cleaned_data["code"],
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
                is_active=form.cleaned_data["is_active"],
                permission_ids=data.get("permissions", []),
                actor=request.user,
                request_meta=request.request_meta,
            )
        except PermissionDenied as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        return JsonResponse({"ok": True})
    else:
        errors = {field: [str(e) for e in err_list] for field, err_list in form.errors.items()}
        return JsonResponse({"errors": errors}, status=400)


@login_required
@crm_permission_required("authorization.roles.manage")
@require_POST
def role_api_toggle(request, role_id):
    role = get_object_or_404(RoleGroup, id=role_id, company=request.company)
    try:
        is_active = RoleService.toggle_role(
            role=role, actor=request.user, request_meta=request.request_meta
        )
        return JsonResponse({"ok": True, "is_active": is_active})
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required
@crm_permission_required("authorization.permissions.manage")
def permission_catalog(request):
    return render(request, "authorization/permission_catalog.html", {
        "permissions": PermissionManagementService.get_permission_catalog(),
    })


@login_required
@crm_permission_required("authorization.roles.manage")
def user_permission_matrix(request, user_id):
    """Show matrix layout page, override saves via AJAX JSON POST."""
    target = get_object_or_404(User, id=user_id, profile__company=request.company)
    can_edit = not RoleService.is_system_admin(target) or RoleService.is_director(request.user)

    if request.method == "POST":
        import json
        if request.content_type == "application/json":
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({"error": "Invalid JSON"}, status=400)
            permission_codes = data.get("permissions", [])
        else:
            permission_codes = request.POST.getlist("permissions")

        # Self-escalation guard: only Directors may edit a System Admin's permissions.
        try:
            RoleService.assert_can_edit_user_permissions(request.user, target)
        except PermissionDenied as exc:
            if request.content_type == "application/json":
                return JsonResponse({"error": str(exc)}, status=403)
            messages.error(request, str(exc))
            return redirect("authorization:user_matrix", user_id=target.id)

        PermissionManagementService.update_user_overrides(
            user=target,
            permission_codes=permission_codes,
            created_by=request.user,
            request_meta=request.request_meta,
        )
        if request.content_type == "application/json":
            return JsonResponse({"ok": True})
        messages.success(request, "Permission overrides updated successfully.")
        return redirect("authorization:user_matrix", user_id=target.id)

    return render(request, "authorization/user_matrix.html", {
        "target": target, "can_edit": can_edit,
    })


@login_required
@crm_permission_required("authorization.roles.manage")
def user_permission_matrix_api(request, user_id):
    target = get_object_or_404(User, id=user_id, profile__company=request.company)
    payload = PermissionManagementService.get_user_permission_matrix_payload(target, request.company)
    return JsonResponse(payload)


@login_required
@crm_permission_required("authorization.roles.manage")
def permission_preview(request, user_id):
    target = get_object_or_404(User, id=user_id, profile__company=request.company)
    return render(request, "authorization/permission_preview.html", {"target": target})


@login_required
@crm_permission_required("authorization.roles.manage")
def permission_preview_api(request, user_id):
    target = get_object_or_404(User, id=user_id, profile__company=request.company)
    payload = PermissionManagementService.get_permission_preview_payload(target)
    return JsonResponse(payload)


@login_required
@crm_permission_required("authorization.roles.manage")
def permission_audit(request):
    return render(request, "authorization/permission_audit.html")


@login_required
@crm_permission_required("authorization.roles.manage")
def permission_audit_api(request):
    from apps.audit.services import AuditService
    filters = {
        "user_id": request.GET.get("user_id"),
        "action": request.GET.get("action"),
        "entity_type": request.GET.get("entity_type"),
        "limit": request.GET.get("limit", 100),
        "page": request.GET.get("page", 1),
    }
    payload = AuditService.get_audit_logs_payload(
        company=request.company,
        filters=filters,
        is_permission_audit=True
    )
    return JsonResponse(payload)
