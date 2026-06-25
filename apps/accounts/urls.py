"""Accounts routes (docs §14). Login/logout via Django auth views."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(
        template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="accounts:login"),
         name="logout"),
    path("users/", views.user_list, name="user_list"),
    path("users/api/", views.user_api_list, name="user_api_list"),
    path("users/api/create/", views.user_api_create, name="user_api_create"),
    path("users/<int:user_id>/api/edit/", views.user_api_edit, name="user_api_edit"),
    path("users/<int:user_id>/api/deactivate/", views.user_api_deactivate,
         name="user_api_deactivate"),
    path("users/<int:user_id>/api/activate/", views.user_api_activate,
         name="user_api_activate"),
    path("users/<int:user_id>/api/delete/", views.user_api_delete,
         name="user_api_delete"),
    path("users/create/", views.user_create, name="user_create"),
    path("users/<int:user_id>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:user_id>/delete/", views.user_delete, name="user_delete"),
    path("users/<int:user_id>/activate/", views.user_activate, name="user_activate"),
    path("teams/", views.team_list, name="team_list"),
    path("teams/create/", views.team_create, name="team_create"),
    path("teams/<uuid:team_id>/edit/", views.team_edit, name="team_edit"),
    path("teams/<uuid:team_id>/delete/", views.team_delete, name="team_delete"),
    path("teams/<uuid:team_id>/activate/", views.team_activate, name="team_activate"),
]
