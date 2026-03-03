from django.core.management.base import BaseCommand, CommandParser

from api_support.services.ingestion import IngestionService


class Command(BaseCommand):
    help = "Ingest API documentation from a JSON file containing a list of {title, content} objects."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("source_name", type=str, help="Name of the documentation source")
        parser.add_argument("json_path", type=str, help="Path to JSON file with docs")

    def handle(self, *args, **options):
        import json
        from pathlib import Path

        source_name: str = options["source_name"]
        json_path = Path(options["json_path"])

        if not json_path.exists():
            self.stderr.write(self.style.ERROR(f"File not found: {json_path}"))
            return

        docs = json.loads(json_path.read_text(encoding="utf-8"))
        ingestion = IngestionService()
        summaries = ingestion.ingest_documents(source_name=source_name, docs=docs)
        for s in summaries:
            self.stdout.write(
                self.style.SUCCESS(f"Ingested document {s.document_id} with {s.chunks_created} chunks.")
            )

