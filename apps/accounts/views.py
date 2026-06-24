"""Accounts views (docs §4.5, §14): thin — permission check, form, service call.
Login uses Django auth; user management uses the custom permission layer."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404

from apps.authorization.decorators import crm_permission_required

from .forms import UserCreateForm, UserEditForm
from .models import User
from .selectors import users_for_company
from .services import UserService


@login_required
@crm_permission_required("admin.users.access")
def user_list(request):
    return render(request, "accounts/user_list.html", {
        "users": users_for_company(request.company),
    })


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
            permission_codes=None,
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
