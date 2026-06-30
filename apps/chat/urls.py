"""Chat routes (docs §14). All namespaced; templates use {% url 'chat:...' %}."""
from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("api/list/", views.chat_list, name="list"),
    path("api/users/", views.chat_users, name="users"),
    path("api/open/", views.chat_open, name="open"),
    path("api/upload/", views.chat_upload, name="upload"),
    path("api/<uuid:conversation_id>/history/", views.chat_history, name="history"),
    path("api/<uuid:conversation_id>/read/", views.chat_mark_read, name="mark_read"),
]
