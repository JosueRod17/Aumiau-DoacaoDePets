from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator

from .cnpj import validar_cnpj


class Ong(models.Model):
    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente'
        APROVADA = 'aprovada', 'Aprovada'
        REJEITADA = 'rejeitada', 'Rejeitada'
        SUSPENSA = 'suspensa', 'Suspensa'

    nome = models.CharField(max_length=120)
    codigo_demonstracao = models.CharField(max_length=40, unique=True, null=True, blank=True, editable=False)
    foto = models.ImageField('foto da ONG', upload_to='ongs/%Y/%m/', blank=True)
    cnpj = models.CharField('CNPJ', max_length=14, unique=True, null=True, blank=True, validators=[validar_cnpj])
    razao_social = models.CharField('razão social consultada', max_length=200, blank=True)
    cnpj_situacao = models.CharField('situação cadastral consultada', max_length=40, blank=True)
    cnpj_consultado_em = models.DateTimeField('consulta de CNPJ realizada em', null=True, blank=True)
    cnpj_confirmado_manualmente = models.BooleanField('CNPJ conferido documentalmente pela equipe', default=False)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)
    descricao = models.TextField(blank=True)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ongs_responsaveis',
    )
    email = models.EmailField('e-mail público', blank=True)
    telefone = models.CharField(
        'telefone público', max_length=11, blank=True,
        validators=[RegexValidator(r'^\d{10,11}$', 'Informe um telefone com DDD.')],
    )
    aprovada = models.BooleanField(default=False)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDENTE,
    )
    motivo_rejeicao = models.TextField(blank=True)
    moderado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ongs_moderadas',
    )
    moderado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'ONG'
        verbose_name_plural = 'ONGs'

    def __str__(self):
        return self.nome

    @property
    def cnpj_requer_conferencia(self):
        return bool(self.cnpj and not self.cnpj_consultado_em and not self.cnpj_confirmado_manualmente)

    def save(self, *args, **kwargs):
        self.aprovada = self.status == self.Status.APROVADA

        if kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(
                kwargs['update_fields']
            ) | {'aprovada'}

        super().save(*args, **kwargs)
