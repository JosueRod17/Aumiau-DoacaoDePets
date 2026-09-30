from django.conf import settings
from django.db import models


class ChamadoAjuda(models.Model):
    class Categoria(models.TextChoices):
        ADOCAO = 'adocao', 'Adoção de pets'
        CADASTRO = 'cadastro', 'Cadastro e anúncios'
        SEGURANCA = 'seguranca', 'Segurança e denúncias'
        SUGESTAO = 'sugestao', 'Sugestões e outros assuntos'

    class Status(models.TextChoices):
        ABERTO = 'aberto', 'Recebido'
        EM_ANALISE = 'em_analise', 'Em análise'
        RESPONDIDO = 'respondido', 'Respondido'
        ENCERRADO = 'encerrado', 'Encerrado'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chamados_ajuda',
        verbose_name='usuário',
    )
    pet = models.ForeignKey(
        'pets.Pet',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chamados_interesse',
        verbose_name='pet do anúncio',
    )
    categoria = models.CharField(max_length=20, choices=Categoria.choices)
    assunto = models.CharField(max_length=150)
    mensagem = models.TextField(max_length=5000)
    contexto_pluttu = models.TextField('conversa com o Pluttu', blank=True, max_length=15000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ABERTO)
    resposta = models.TextField(blank=True, max_length=10000)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em', '-pk']
        verbose_name = 'chamado de ajuda'
        verbose_name_plural = 'chamados de ajuda'

    def __str__(self):
        return f'#{self.pk} — {self.assunto}'


class SolicitacaoAdocao(models.Model):
    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Em análise'
        APROVADA = 'aprovada', 'Aprovada'
        RECUSADA = 'recusada', 'Recusada'
        CANCELADA = 'cancelada', 'Cancelada'

    pet = models.ForeignKey('pets.Pet', on_delete=models.CASCADE, related_name='solicitacoes_adocao')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='solicitacoes_adocao',
        verbose_name='solicitante',
    )
    mensagem = models.TextField(max_length=5000)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDENTE)
    resposta = models.TextField(blank=True, max_length=5000)
    analisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='adocoes_analisadas',
    )
    analisado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em', '-pk']
        verbose_name = 'solicitação de adoção'
        verbose_name_plural = 'solicitações de adoção'
        constraints = [
            models.UniqueConstraint(
                fields=['pet', 'usuario'], condition=models.Q(status='pendente'),
                name='adocao_pendente_pet_usuario',
            ),
        ]

    def __str__(self):
        return f'#{self.pk} — Adoção de {self.pet.nome}'
