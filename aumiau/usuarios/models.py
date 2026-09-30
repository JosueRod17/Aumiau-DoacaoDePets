from django.conf import settings
from django.db import models


UF_CHOICES = [
    ('AC', 'AC'), ('AL', 'AL'), ('AP', 'AP'), ('AM', 'AM'),
    ('BA', 'BA'), ('CE', 'CE'), ('DF', 'DF'), ('ES', 'ES'),
    ('GO', 'GO'), ('MA', 'MA'), ('MT', 'MT'), ('MS', 'MS'),
    ('MG', 'MG'), ('PA', 'PA'), ('PB', 'PB'), ('PR', 'PR'),
    ('PE', 'PE'), ('PI', 'PI'), ('RJ', 'RJ'), ('RN', 'RN'),
    ('RS', 'RS'), ('RO', 'RO'), ('RR', 'RR'), ('SC', 'SC'),
    ('SP', 'SP'), ('SE', 'SE'), ('TO', 'TO'),
]


class Perfil(models.Model):
    class Situacao(models.TextChoices):
        ATIVA = 'ativa', 'Ativa'
        SUSPENSA = 'suspensa', 'Suspensa'
        BANIDA = 'banida', 'Banida'
        EXCLUIDA = 'excluida', 'Excluída'

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil',
    )

    telefone = models.CharField(max_length=11)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2, choices=UF_CHOICES)

    aceitou_termos_em = models.DateTimeField()
    versao_termos = models.CharField(max_length=20)

    cpf_hash = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    cpf_final = models.CharField(max_length=4, blank=True, editable=False)
    situacao = models.CharField(max_length=10, choices=Situacao.choices, default=Situacao.ATIVA)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Perfil de {self.usuario.get_username()}'

    @property
    def cpf_mascarado(self):
        return f'***.***.*{self.cpf_final[:2]}-{self.cpf_final[2:]}' if self.cpf_final else 'Não informado'


class DocumentoBloqueado(models.Model):
    """Identificador irreversível para impedir novo cadastro após banimento."""
    cpf_hash = models.CharField(max_length=64, unique=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'bloqueio de documento'
        verbose_name_plural = 'bloqueios de documentos'

    def __str__(self):
        return f'Bloqueio #{self.pk}'


class ContaGoogle(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conta_google')
    subject = models.CharField(max_length=255, unique=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Google de {self.usuario.get_username()}'
