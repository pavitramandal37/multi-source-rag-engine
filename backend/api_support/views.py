import dataclasses
from pathlib import Path

from django.conf import settings
from django.db.models import Count
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from api_support.models import Source
from api_support.serializers import (
    ChatRequestSerializer,
    ChatResponseSerializer,
    IngestRequestSerializer,
    IngestResponseSerializer,
    IngestURLRequestSerializer,
    IngestionResultSerializer,
    SourceSerializer,
)
from api_support.services.ingestion import IngestionService
from api_support.services.llm_client import LLMUnavailableError
from api_support.services.markdown_ingestion import MarkdownIngestionService
from api_support.services.pdf_ingestion import PDFIngestionService
from api_support.services.rag_pipeline import RAGPipeline
from api_support.services.url_ingestion import URLIngestionService


class ChatView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        pipeline = RAGPipeline()
        try:
            rag_response = pipeline.answer(
                question=data["query"],
                conversation_id=data.get("conversation_id"),
                source_ids=data.get("source_ids") or None,
            )
        except LLMUnavailableError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        resp_serializer = ChatResponseSerializer({
            "answer": rag_response.answer,
            "sources": rag_response.sources,
            "conversation_id": rag_response.conversation_id,
            "confidence": rag_response.confidence,
        })
        return Response(resp_serializer.data, status=status.HTTP_200_OK)


class IngestDocsView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = IngestRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        ingestion = IngestionService()
        summaries = ingestion.ingest_documents(source_name=data["source_name"], docs=data["docs"])
        resp = {
            "summaries": [
                {"document_id": s.document_id, "chunks_created": s.chunks_created}
                for s in summaries
            ]
        }
        return Response(IngestResponseSerializer(resp).data, status=status.HTTP_201_CREATED)


class SourceListView(APIView):
    def get(self, request):
        sources = Source.objects.annotate(
            document_count=Count("documents")
        ).order_by("-created_at")
        return Response(SourceSerializer(sources, many=True).data)


class SourceDeleteView(APIView):
    def delete(self, request, pk):
        try:
            source = Source.objects.get(pk=pk)
        except Source.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        source.delete()  # CASCADE: Source → Document → DocumentChunk
        return Response(status=status.HTTP_204_NO_CONTENT)


class IngestURLView(APIView):
    def post(self, request):
        serializer = IngestURLRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = URLIngestionService()
        result = service.ingest_url(
            name=data["name"],
            url=data["url"],
            crawl_depth=data["crawl_depth"],
        )
        return Response(IngestionResultSerializer(dataclasses.asdict(result)).data, status=status.HTTP_201_CREATED)


class IngestFileView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        name = request.data.get("name", "").strip()
        if not name:
            return Response({"error": "name is required"}, status=status.HTTP_400_BAD_REQUEST)

        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response({"error": "file is required"}, status=status.HTTP_400_BAD_REQUEST)

        filename = uploaded.name
        ext = Path(filename).suffix.lower()
        if ext not in (".pdf", ".md"):
            return Response(
                {"error": "Only .pdf and .md files are supported"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        upload_dir = Path(settings.MEDIA_ROOT) / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        save_path = upload_dir / filename

        with open(save_path, "wb") as f:
            for chunk in uploaded.chunks():
                f.write(chunk)

        try:
            if ext == ".pdf":
                result = PDFIngestionService().ingest_pdf(
                    name=name, pdf_path=save_path, filename=filename
                )
            else:
                result = MarkdownIngestionService().ingest_markdown(
                    name=name, md_path=save_path, filename=filename
                )
        except Exception as exc:
            save_path.unlink(missing_ok=True)
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(IngestionResultSerializer(dataclasses.asdict(result)).data, status=status.HTTP_201_CREATED)
