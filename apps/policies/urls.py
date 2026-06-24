"""Policy routes (docs §14)."""
from django.urls import path

from . import views

app_name = "policies"

urlpatterns = [
    path("", views.policy_list, name="list"),
    path("<uuid:policy_id>/edit/", views.policy_edit, name="edit"),
]
