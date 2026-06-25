"""Authorization routes (docs §14)."""
from django.urls import path

from . import views

app_name = "authorization"

urlpatterns = [
    path("roles/", views.role_list, name="role_list"),
    path("roles/api/", views.role_api_list, name="role_api_list"),
    path("roles/api/create/", views.role_api_create, name="role_api_create"),
    path("roles/<uuid:role_id>/api/edit/", views.role_api_edit, name="role_api_edit"),
    path("roles/<uuid:role_id>/api/toggle/", views.role_api_toggle, name="role_api_toggle"),
    path("roles/create/", views.role_create, name="role_create"),
    path("roles/<uuid:role_id>/edit/", views.role_edit, name="role_edit"),
    path("roles/<uuid:role_id>/toggle/", views.role_toggle, name="role_toggle"),
    path("permissions/", views.permission_catalog, name="permission_catalog"),
    path("users/<int:user_id>/matrix/", views.user_permission_matrix,
         name="user_matrix"),
    path("users/<int:user_id>/matrix/api/", views.user_permission_matrix_api,
         name="user_matrix_api"),
    path("users/<int:user_id>/preview/", views.permission_preview,
         name="permission_preview"),
    path("users/<int:user_id>/preview/api/", views.permission_preview_api,
         name="permission_preview_api"),
    path("audit/", views.permission_audit, name="permission_audit"),
    path("audit/api/", views.permission_audit_api, name="permission_audit_api"),
]
