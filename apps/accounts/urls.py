"""Accounts routes (docs §14). Login/logout via Django auth views."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
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
    path("teams/api/", views.team_api_list, name="team_api_list"),
    path("teams/api/create/", views.team_api_create, name="team_api_create"),
    path("teams/<uuid:team_id>/api/edit/", views.team_api_edit, name="team_api_edit"),
    path("teams/<uuid:team_id>/api/delete/", views.team_api_delete, name="team_api_delete"),
    path("teams/<uuid:team_id>/api/activate/", views.team_api_activate, name="team_api_activate"),
    path("teams/create/", views.team_create, name="team_create"),
    path("teams/<uuid:team_id>/edit/", views.team_edit, name="team_edit"),
    path("teams/<uuid:team_id>/delete/", views.team_delete, name="team_delete"),
    path("teams/<uuid:team_id>/activate/", views.team_activate, name="team_activate"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/api/", views.profile_api, name="profile_api"),
    path("change-password/", views.change_password_view, name="change_password"),
    path("change-password/api/", views.change_password_api, name="change_password_api"),
    path("brokers/", views.broker_list, name="broker_list"),
    path("brokers/api/", views.broker_api_list, name="broker_api_list"),
    path("brokers/api/create/", views.broker_api_create, name="broker_api_create"),
    path("brokers/<uuid:broker_id>/api/edit/", views.broker_api_edit, name="broker_api_edit"),
    path("brokers/<uuid:broker_id>/api/delete/", views.broker_api_delete, name="broker_api_delete"),
    path("agencies/api/", views.agency_api_list, name="agency_api_list"),
    path("agencies/api/create/", views.agency_api_create, name="agency_api_create"),
    path("agencies/<uuid:agency_id>/api/edit/", views.agency_api_edit, name="agency_api_edit"),
    path("agencies/<uuid:agency_id>/api/delete/", views.agency_api_delete, name="agency_api_delete"),
]
