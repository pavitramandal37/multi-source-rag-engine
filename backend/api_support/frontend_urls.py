from django.urls import path

from api_support.frontend_views import ChatPageView, SetupPageView, SourcesPageView

urlpatterns = [
    path("", ChatPageView.as_view(), name="chat-page"),
    path("sources/", SourcesPageView.as_view(), name="sources-page"),
    path("setup/", SetupPageView.as_view(), name="setup-page"),
]
