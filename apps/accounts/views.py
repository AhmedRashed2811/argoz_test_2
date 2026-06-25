"""Accounts views (docs §4.5, §14): thin — permission check, form, service call.
Login uses Django auth; user management uses the custom permission layer."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_POST

from apps.authorization.decorators import crm_permission_required

from .forms import TeamForm, UserCreateForm, UserEditForm
from .models import Team, User
from .selectors import teams_for_company, users_for_company
from django.views.decorators.csrf import ensure_csrf_cookie
from .services import TeamService, UserService


@ensure_csrf_cookie
def login_view(request):
    if request.method == "POST":
        import json
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        
        email = data.get("email", "").strip()
        password = data.get("password", "")
        remember = data.get("remember", False)
        
        if not email or not password:
            return JsonResponse({"error": "Email and password are required."}, status=400)
            
        user, error = UserService.login_user(request=request, email=email, password=password, remember=remember)
        if user:
            return JsonResponse({"ok": True})
        return JsonResponse({"error": error}, status=400)
        
    return render(request, "accounts/login.html")



@login_required
@crm_permission_required("admin.users.access")
def user_list(request):
    context = UserService.get_user_creation_context(company=request.company)
    return render(request, "accounts/user_list.html", context)


@login_required
@crm_permission_required("admin.users.access")
def user_api_list(request):
    return JsonResponse(UserService.directory_payload(company=request.company))


@login_required
@crm_permission_required("admin.users.delete")
@require_POST
def user_api_deactivate(request, user_id):
    target_user = get_object_or_404(User, id=user_id, profile__company=request.company)
    if target_user == request.user:
        return JsonResponse(
            {"error": "You cannot deactivate your own account."}, status=400
        )
    UserService.delete_user(
        user=target_user, actor=request.user,
        request_meta=getattr(request, "request_meta", None),
    )
    return JsonResponse({"ok": True})


@login_required
@crm_permission_required("admin.users.update")
@require_POST
def user_api_activate(request, user_id):
    target_user = get_object_or_404(User, id=user_id, profile__company=request.company)
    UserService.activate_user(
        user=target_user, actor=request.user,
        request_meta=getattr(request, "request_meta", None),
    )
    return JsonResponse({"ok": True})


@login_required
@crm_permission_required("admin.users.delete")
@require_POST
def user_api_delete(request, user_id):
    target_user = get_object_or_404(User, id=user_id, profile__company=request.company)
    if target_user == request.user:
        return JsonResponse(
            {"error": "You cannot delete your own account."}, status=400
        )
    UserService.destroy_user(
        user=target_user, actor=request.user,
        request_meta=getattr(request, "request_meta", None),
    )
    return JsonResponse({"ok": True})



@login_required
@crm_permission_required("admin.users.create")
@require_POST
def user_api_create(request):
    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    
    form = UserCreateForm(data, company=request.company)
    if form.is_valid():
        cleaned = form.cleaned_data
        UserService.create_user(
            company=request.company,
            email=cleaned["email"],
            password=cleaned["password"],
            default_role=cleaned["default_role"],
            first_name=cleaned["first_name"],
            last_name=cleaned["last_name"],
            phone=cleaned["phone"],
            job_title=cleaned["job_title"],
            permission_codes=data.get("permissions"),
            created_by=request.user,
            request_meta=request.request_meta,
        )
        return JsonResponse({"ok": True})
    else:
        errors = {field: [str(e) for e in err_list] for field, err_list in form.errors.items()}
        return JsonResponse({"errors": errors}, status=400)


@login_required
@crm_permission_required("admin.users.update")
@require_POST
def user_api_edit(request, user_id):
    import json
    target_user = get_object_or_404(User, id=user_id, profile__company=request.company)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    
    form = UserEditForm(data, company=request.company, user_instance=target_user)
    if form.is_valid():
        cleaned = form.cleaned_data
        UserService.update_user(
            user=target_user,
            email=cleaned["email"],
            password=cleaned.get("password") or None,
            default_role=cleaned["default_role"],
            first_name=cleaned["first_name"],
            last_name=cleaned["last_name"],
            phone=cleaned["phone"],
            job_title=cleaned["job_title"],
            permission_codes=data.get("permissions"),
            created_by=request.user,
            request_meta=request.request_meta,
        )
        return JsonResponse({"ok": True})
    else:
        errors = {field: [str(e) for e in err_list] for field, err_list in form.errors.items()}
        return JsonResponse({"errors": errors}, status=400)


@login_required
@crm_permission_required("admin.users.create")
def user_create(request):
    form = UserCreateForm(request.POST or None, company=request.company)
    
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        UserService.create_user(
            company=request.company, email=data["email"], password=data["password"],
            default_role=data["default_role"], first_name=data["first_name"],
            last_name=data["last_name"], phone=data["phone"], job_title=data["job_title"],
            permission_codes=request.POST.getlist("permissions"), created_by=request.user,
            request_meta=request.request_meta
        )
        messages.success(request, "User created.")
        return redirect("accounts:user_list")
        
    context = UserService.get_user_creation_context(company=request.company)
    context["form"] = form
    return render(request, "accounts/user_form.html", context)


@login_required
@crm_permission_required("admin.users.update")
def user_edit(request, user_id):
    target_user = get_object_or_404(User, id=user_id, profile__company=request.company)
    profile = target_user.profile
    initial_data = {
        "email": target_user.email,
        "first_name": target_user.first_name,
        "last_name": target_user.last_name,
        "phone": target_user.phone,
        "job_title": profile.job_title,
        "default_role": profile.default_role,
    }
    form = UserEditForm(request.POST or None, initial=initial_data, company=request.company, user_instance=target_user)
    
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        UserService.update_user(
            user=target_user,
            email=data["email"],
            password=data.get("password") or None,
            default_role=data["default_role"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            phone=data["phone"],
            job_title=data["job_title"],
            permission_codes=request.POST.getlist("permissions"),
            created_by=request.user,
            request_meta=request.request_meta
        )
        messages.success(request, "User updated successfully.")
        return redirect("accounts:user_list")
        
    context = UserService.get_user_creation_context(company=request.company)
    context["form"] = form
    context["user_instance"] = target_user
    
    from apps.authorization.services import EffectivePermissionResolver
    context["user_active_permissions"] = EffectivePermissionResolver.get_codes(target_user)
    context["is_edit_mode"] = True
    return render(request, "accounts/user_form.html", context)


@login_required
@crm_permission_required("admin.users.delete")
def user_delete(request, user_id):
    target_user = get_object_or_404(User, id=user_id, profile__company=request.company)
    if target_user == request.user:
        messages.error(request, "You cannot delete/deactivate your own account.")
    else:
        UserService.delete_user(user=target_user, actor=request.user, request_meta=request.request_meta)
        messages.success(request, f"User {target_user.email} deactivated successfully.")
    return redirect("accounts:user_list")


@login_required
@crm_permission_required("admin.users.update")
def user_activate(request, user_id):
    target_user = get_object_or_404(User, id=user_id, profile__company=request.company)
    UserService.activate_user(user=target_user, actor=request.user, request_meta=request.request_meta)
    messages.success(request, f"User {target_user.email} activated successfully.")
    return redirect("accounts:user_list")


# ── Sales Teams ──────────────────────────────────────────────────────────────

@login_required
@crm_permission_required("admin.teams.access")
def team_list(request):
    return render(request, "accounts/team_list.html")


@login_required
@crm_permission_required("admin.teams.create")
def team_create(request):
    context = TeamService.get_team_context(company=request.company)
    import json
    context["available_heads_json"] = json.dumps([
        {"id": u.id, "email": u.email, "full_name": u.get_full_name()}
        for u in context["available_heads"]
    ])
    context["available_members_json"] = json.dumps([
        {"id": u.id, "email": u.email, "full_name": u.get_full_name()}
        for u in context["available_members"]
    ])
    context["is_edit_mode"] = False
    return render(request, "accounts/team_form.html", context)


@login_required
@crm_permission_required("admin.teams.update")
def team_edit(request, team_id):
    team = get_object_or_404(Team, id=team_id, company=request.company)
    context = TeamService.get_team_context(company=request.company, team=team)
    import json
    context["available_heads_json"] = json.dumps([
        {"id": u.id, "email": u.email, "full_name": u.get_full_name()}
        for u in context["available_heads"]
    ])
    context["available_members_json"] = json.dumps([
        {"id": u.id, "email": u.email, "full_name": u.get_full_name()}
        for u in context["available_members"]
    ])
    context["current_head_ids_json"] = json.dumps(list(context["current_head_ids"]))
    context["current_member_ids_json"] = json.dumps(list(context["current_member_ids"]))
    context["team_instance"] = team
    context["is_edit_mode"] = True
    return render(request, "accounts/team_form.html", context)


@login_required
@crm_permission_required("admin.teams.delete")
def team_delete(request, team_id):
    team = get_object_or_404(Team, id=team_id, company=request.company)
    TeamService.delete_team(user=team, actor=request.user, request_meta=request.request_meta)
    messages.success(request, f"Team \"{team.name}\" deleted.")
    return redirect("accounts:team_list")


@login_required
@crm_permission_required("admin.teams.update")
def team_activate(request, team_id):
    team = get_object_or_404(Team, id=team_id, company=request.company)
    TeamService.activate_team(team=team, actor=request.user, request_meta=request.request_meta)
    messages.success(request, f"Team \"{team.name}\" activated.")
    return redirect("accounts:team_list")


@login_required
@crm_permission_required("admin.teams.access")
def team_api_list(request):
    return JsonResponse(TeamService.list_payload(company=request.company))


@login_required
@crm_permission_required("admin.teams.create")
@require_POST
def team_api_create(request):
    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    form = TeamForm(data)
    if form.is_valid():
        cleaned = form.cleaned_data
        TeamService.create_team(
            company=request.company,
            name=cleaned["name"],
            region=cleaned["region"],
            order_index=cleaned["order_index"],
            head_ids=data.get("heads", []),
            member_ids=data.get("members", []),
            actor=request.user,
            request_meta=request.request_meta,
        )
        return JsonResponse({"ok": True})
    else:
        errors = {field: [str(e) for e in err_list] for field, err_list in form.errors.items()}
        return JsonResponse({"errors": errors}, status=400)


@login_required
@crm_permission_required("admin.teams.update")
@require_POST
def team_api_edit(request, team_id):
    import json
    team = get_object_or_404(Team, id=team_id, company=request.company)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    form = TeamForm(data)
    if form.is_valid():
        cleaned = form.cleaned_data
        TeamService.update_team(
            team=team,
            name=cleaned["name"],
            region=cleaned["region"],
            order_index=cleaned["order_index"],
            head_ids=data.get("heads", []),
            member_ids=data.get("members", []),
            actor=request.user,
            request_meta=request.request_meta,
        )
        return JsonResponse({"ok": True})
    else:
        errors = {field: [str(e) for e in err_list] for field, err_list in form.errors.items()}
        return JsonResponse({"errors": errors}, status=400)


@login_required
@crm_permission_required("admin.teams.delete")
@require_POST
def team_api_delete(request, team_id):
    team = get_object_or_404(Team, id=team_id, company=request.company)
    TeamService.delete_team(
        team=team, actor=request.user,
        request_meta=getattr(request, "request_meta", None),
    )
    return JsonResponse({"ok": True})


@login_required
@crm_permission_required("admin.teams.update")
@require_POST
def team_api_activate(request, team_id):
    team = get_object_or_404(Team, id=team_id, company=request.company)
    TeamService.activate_team(
        team=team, actor=request.user,
        request_meta=getattr(request, "request_meta", None),
    )
    return JsonResponse({"ok": True})


@login_required
def profile_view(request):
    return render(request, "accounts/profile.html")


@login_required
def profile_api(request):
    from apps.authorization.services import PermissionManagementService
    payload = PermissionManagementService.get_permission_preview_payload(request.user)
    return JsonResponse(payload)


@login_required
def change_password_view(request):
    return render(request, "accounts/change_password.html")


@login_required
@require_POST
def change_password_api(request):
    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not current_password or not new_password:
        return JsonResponse({"error": "Both current and new passwords are required."}, status=400)

    if len(new_password) < 8:
        return JsonResponse({"error": "New password must be at least 8 characters long."}, status=400)

    success, error = UserService.change_password(
        user=request.user,
        current_password=current_password,
        new_password=new_password,
        request_meta=getattr(request, "request_meta", None),
    )
    if success:
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, request.user)
        return JsonResponse({"ok": True})
    return JsonResponse({"error": error}, status=400)

