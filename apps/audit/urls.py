"""Audit routes (docs §14)."""
from django.urls import path

from . import views

app_name = "audit"

urlpatterns = [
    path("", views.audit_list, name="list"),
    path("api/", views.audit_api_list, name="api_list"),
]
