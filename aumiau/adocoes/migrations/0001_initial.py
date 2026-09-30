import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name='ChamadoAjuda',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('categoria', models.CharField(choices=[('adocao', 'Adoção de pets'), ('cadastro', 'Cadastro e anúncios'), ('seguranca', 'Segurança e denúncias'), ('sugestao', 'Sugestões e outros assuntos')], max_length=20)),
                ('assunto', models.CharField(max_length=150)),
                ('mensagem', models.TextField(max_length=5000)),
                ('status', models.CharField(choices=[('aberto', 'Recebido'), ('em_analise', 'Em análise'), ('respondido', 'Respondido'), ('encerrado', 'Encerrado')], default='aberto', max_length=20)),
                ('resposta', models.TextField(blank=True, max_length=10000)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chamados_ajuda', to=settings.AUTH_USER_MODEL, verbose_name='usuário')),
            ],
            options={
                'verbose_name': 'chamado de ajuda',
                'verbose_name_plural': 'chamados de ajuda',
                'ordering': ['-criado_em', '-pk'],
            },
        ),
    ]
