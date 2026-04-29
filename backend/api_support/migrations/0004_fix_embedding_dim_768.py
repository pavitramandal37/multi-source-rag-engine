import pgvector.django.vector
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api_support', '0003_alter_documentchunk_embedding_768'),
    ]

    operations = [
        migrations.AlterField(
            model_name='documentchunk',
            name='embedding',
            field=pgvector.django.vector.VectorField(dimensions=768),
        ),
    ]
