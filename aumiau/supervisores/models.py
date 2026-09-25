from django.conf import settings
from django.db import models


class RegistroAtividade(models.Model):
    class Acao(models.TextChoices):
        CADASTROU = 'cadastrou', 'Cadastrou'
        EDITOU = 'editou', 'Editou'
        PUBLICOU = 'publicou', 'Publicou'
        REJEITOU = 'rejeitou', 'Rejeitou'
        ADOTOU = 'adotou', 'Marcou como adotado'
        ARQUIVOU = 'arquivou', 'Arquivou'
        REABRIU = 'reabriu', 'Reabriu'
        APROVOU = 'aprovou', 'Aprovou'
        ATIVOU = 'ativou', 'Ativou'
        DESATIVOU = 'desativou', 'Desativou'
        PROMOVEU = 'promoveu', 'Promoveu'
        REMOVEU_ACESSO = 'removeu_acesso', 'Removeu acesso'

    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='atividades_de_supervisao',
    )

    acao = models.CharField(
        max_length=20,
        choices=Acao.choices,
    )

    entidade = models.CharField(max_length=40)
    objeto_id = models.PositiveBigIntegerField(null=True, blank=True)
    descricao = models.CharField(max_length=255)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        verbose_name = 'registro de atividade'
        verbose_name_plural = 'registros de atividades'
        permissions = (
            ('moderar_pet', 'Pode moderar anúncios de pets'),
            ('moderar_ong', 'Pode moderar cadastros de ONGs'),
            ('gerenciar_usuarios', 'Pode ativar e inativar usuários'),
        )

    def __str__(self):
        return self.descricao
