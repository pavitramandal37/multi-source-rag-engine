from django.views.generic import TemplateView

from api_support.models import Source


class ChatPageView(TemplateView):
    template_name = "chat.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["sources"] = Source.objects.order_by("name")
        ctx["app_title"] = "General Purpose Grounded RAG Chat"
        return ctx


class SourcesPageView(TemplateView):
    template_name = "sources.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["app_title"] = "Manage Sources"
        return ctx


class SetupPageView(TemplateView):
    template_name = "setup.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["app_title"] = "Setup Guide"
        return ctx
