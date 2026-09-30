from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('adocoes', '0001_initial')]

    operations = [
        migrations.AddField(
            model_name='chamadoajuda',
            name='contexto_pluttu',
            field=models.TextField(blank=True, max_length=15000, verbose_name='conversa com o Pluttu'),
        ),
    ]
