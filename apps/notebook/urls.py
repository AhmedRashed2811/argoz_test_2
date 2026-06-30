"""Notebook routes. Namespaced; templates use {% url 'notebook:...' %}."""
from django.urls import path

from . import views

app_name = "notebook"

urlpatterns = [
    path("api/list/", views.note_list, name="list"),
    path("api/create/", views.note_create, name="create"),
    path("api/<uuid:note_id>/update/", views.note_update, name="update"),
    path("api/<uuid:note_id>/delete/", views.note_delete, name="delete"),
]
