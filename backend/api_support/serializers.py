from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    query = serializers.CharField()
    conversation_id = serializers.IntegerField(required=False, allow_null=True)


class ChatResponseSerializer(serializers.Serializer):
    answer = serializers.CharField()
    sources = serializers.ListField(child=serializers.DictField())
    conversation_id = serializers.IntegerField()


class IngestDocSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True)
    content = serializers.CharField()


class IngestRequestSerializer(serializers.Serializer):
    source_name = serializers.CharField()
    docs = IngestDocSerializer(many=True)


class IngestResponseSerializer(serializers.Serializer):
    summaries = serializers.ListField(child=serializers.DictField())

