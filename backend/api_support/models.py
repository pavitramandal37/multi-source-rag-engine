from django.conf import settings
from django.db import models
from pgvector.django import VectorField


class Source(models.Model):
    TYPE_URL = "url"
    TYPE_PDF = "pdf"
    TYPE_MARKDOWN = "markdown"
    TYPE_JSON = "json"

    TYPE_CHOICES = [
        (TYPE_URL, "URL"),
        (TYPE_PDF, "PDF"),
        (TYPE_MARKDOWN, "Markdown"),
        (TYPE_JSON, "JSON"),
    ]

    name = models.CharField(max_length=255)
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    origin = models.CharField(max_length=2048)  # URL or original filename
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.type})"


class Document(models.Model):
    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
        related_name="documents",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    source_name = models.CharField(max_length=255, blank=True)  # kept for backwards compat
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.title


class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    embedding = VectorField(dimensions=getattr(settings, "VECTOR_DIMENSIONS", 768))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["document", "chunk_index"]),
        ]


class Conversation(models.Model):
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.title or f"Conversation {self.pk}"


class Message(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"

    ROLE_CHOICES = [
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
