from django.db import models
from django.conf import settings


class Ong(models.Model):
    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente'
        APROVADA = 'aprovada', 'Aprovada'
        REJEITADA = 'rejeitada', 'Rejeitada'
        SUSPENSA = 'suspensa', 'Suspensa'

    nome = models.CharField(max_length=120)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)
    descricao = models.TextField(blank=True)
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

    def save(self, *args, **kwargs):
        self.aprovada = self.status == self.Status.APROVADA

        if kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(
                kwargs['update_fields']
            ) | {'aprovada'}

        super().save(*args, **kwargs)
