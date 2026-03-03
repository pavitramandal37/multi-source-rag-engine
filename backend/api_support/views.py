from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api_support.serializers import (
    ChatRequestSerializer,
    ChatResponseSerializer,
    IngestRequestSerializer,
    IngestResponseSerializer,
)
from api_support.services.ingestion import IngestionService
from api_support.services.rag_pipeline import RAGPipeline


class ChatView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        pipeline = RAGPipeline()
        rag_response = pipeline.answer(
            question=data["query"],
            conversation_id=data.get("conversation_id"),
        )

        resp_serializer = ChatResponseSerializer(
            {
                "answer": rag_response.answer,
                "sources": rag_response.sources,
                "conversation_id": rag_response.conversation_id,
            }
        )
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
                {"document_id": s.document_id, "chunks_created": s.chunks_created} for s in summaries
            ]
        }
        resp_serializer = IngestResponseSerializer(resp)
        return Response(resp_serializer.data, status=status.HTTP_201_CREATED)

