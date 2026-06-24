"""Accounts views (docs §4.5, §14): thin — permission check, form, service call.
Login uses Django auth; user management uses the custom permission layer."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.authorization.decorators import crm_permission_required

from .forms import UserCreateForm
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
        )
        messages.success(request, "User created.")
        return redirect("accounts:user_list")
    return render(request, "accounts/user_form.html", {"form": form})
