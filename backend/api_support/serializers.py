from rest_framework import serializers


# ── Existing chat serializers (updated) ──────────────────────────────────────

class ChatRequestSerializer(serializers.Serializer):
    query = serializers.CharField()
    conversation_id = serializers.IntegerField(required=False, allow_null=True)
    source_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        default=list,
    )


class SourceCitationSerializer(serializers.Serializer):
    document_id = serializers.IntegerField()
    document_title = serializers.CharField()
    chunk_index = serializers.IntegerField()
    snippet = serializers.CharField()
    citation_url = serializers.CharField(allow_blank=True)


class ChatResponseSerializer(serializers.Serializer):
    answer = serializers.CharField()
    sources = SourceCitationSerializer(many=True)
    conversation_id = serializers.IntegerField()
    confidence = serializers.CharField()  # "high" | "low" | "none"


# ── Existing ingest-docs serializers (unchanged) ─────────────────────────────

class IngestDocSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True)
    content = serializers.CharField()


class IngestRequestSerializer(serializers.Serializer):
    source_name = serializers.CharField()
    docs = IngestDocSerializer(many=True)


class IngestResponseSerializer(serializers.Serializer):
    summaries = serializers.ListField(child=serializers.DictField())


# ── New source serializers ────────────────────────────────────────────────────

class SourceSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    type = serializers.CharField()
    origin = serializers.CharField()
    created_at = serializers.DateTimeField(read_only=True)
    document_count = serializers.IntegerField(read_only=True)


class IngestURLRequestSerializer(serializers.Serializer):
    name = serializers.CharField()
    url = serializers.URLField()
    crawl_depth = serializers.IntegerField(required=False, default=2, min_value=0, max_value=5)


class IngestionResultSerializer(serializers.Serializer):
    source_id = serializers.IntegerField()
    documents_created = serializers.IntegerField()
    chunks_created = serializers.IntegerField()
