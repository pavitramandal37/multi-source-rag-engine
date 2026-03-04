from django.urls import path

from api_support.views import ChatView, IngestDocsView

urlpatterns = [
    path("chat/", ChatView.as_view(), name="chat"),
    path("docs/ingest/", IngestDocsView.as_view(), name="docs-ingest"),
]

