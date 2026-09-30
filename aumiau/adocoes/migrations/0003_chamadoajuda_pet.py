from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('adocoes', '0002_chamadoajuda_contexto_pluttu'),
        ('pets', '0005_pet_codigo_demonstracao'),
    ]

    operations = [
        migrations.AddField(
            model_name='chamadoajuda',
            name='pet',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='chamados_interesse',
                to='pets.pet',
                verbose_name='pet do anúncio',
            ),
        ),
    ]
