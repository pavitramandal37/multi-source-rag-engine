from django.urls import path

from api_support.views import (
    ChatView,
    IngestDocsView,
    IngestFileView,
    IngestURLView,
    SourceDeleteView,
    SourceListView,
)

urlpatterns = [
    path("chat/", ChatView.as_view(), name="chat"),
    path("docs/ingest/", IngestDocsView.as_view(), name="docs-ingest"),
    path("sources/", SourceListView.as_view(), name="source-list"),
    # specific ingest paths must come before <int:pk> to avoid routing conflicts
    path("sources/ingest/url/", IngestURLView.as_view(), name="ingest-url"),
    path("sources/ingest/file/", IngestFileView.as_view(), name="ingest-file"),
    path("sources/<int:pk>/", SourceDeleteView.as_view(), name="source-delete"),
]
