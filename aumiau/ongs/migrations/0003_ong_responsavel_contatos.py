import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ongs', '0002_ong_atualizado_em_ong_moderado_em_ong_moderado_por_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='ong', name='responsavel',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ongs_responsaveis', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='ong', name='email',
            field=models.EmailField(blank=True, max_length=254, verbose_name='e-mail público'),
        ),
        migrations.AddField(
            model_name='ong', name='telefone',
            field=models.CharField(blank=True, max_length=11, validators=[django.core.validators.RegexValidator(r'^\d{10,11}$', 'Informe um telefone com DDD.')], verbose_name='telefone público'),
        ),
    ]
