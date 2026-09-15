from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models

from usuarios.models import UF_CHOICES


class Pet(models.Model):
    class Especie(models.TextChoices):
        CACHORRO = 'cachorro', 'Cachorro'
        GATO = 'gato', 'Gato'
        OUTRO = 'outro', 'Outro'

    class Genero(models.TextChoices):
        MACHO = 'macho', 'Macho'
        FEMEA = 'femea', 'Fêmea'
        NAO_INFORMADO = 'nao_informado', 'Não informado'

    class Porte(models.TextChoices):
        PEQUENO = 'pequeno', 'Pequeno'
        MEDIO = 'medio', 'Médio'
        GRANDE = 'grande', 'Grande'
        NAO_INFORMADO = 'nao_informado', 'Não informado'

    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente'
        PUBLICADO = 'publicado', 'Publicado'
        ADOTADO = 'adotado', 'Adotado'
        REJEITADO = 'rejeitado', 'Rejeitado'
        ARQUIVADO = 'arquivado', 'Arquivado'

    nome = models.CharField(max_length=80)

    especie = models.CharField(
        max_length=10,
        choices=Especie.choices,
    )

    raca = models.CharField(
        'raça',
        max_length=80,
        default='Sem raça definida',
    )

    genero = models.CharField(
        'gênero',
        max_length=15,
        choices=Genero.choices,
        default=Genero.NAO_INFORMADO,
    )

    porte = models.CharField(
        max_length=15,
        choices=Porte.choices,
        default=Porte.NAO_INFORMADO,
    )

    idade_anos = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(40)],
    )

    idade_meses = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(11)],
    )

    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pets_sob_responsabilidade',
    )

    ong = models.ForeignKey(
        'ongs.Ong',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pets',
    )

    cidade = models.CharField(max_length=100)

    estado = models.CharField(
        max_length=2,
        choices=UF_CHOICES,
    )

    descricao = models.TextField(
        'descrição',
        default='',
    )

    vacinado = models.BooleanField(default=False)
    castrado = models.BooleanField(default=False)
    vermifugado = models.BooleanField(default=False)
    microchipado = models.BooleanField(default=False)

    necessidades_especiais = models.BooleanField(default=False)

    descricao_necessidades_especiais = models.TextField(
        'descrição das necessidades especiais',
        blank=True,
    )

    foto_principal = models.ImageField(
        upload_to='pets/principais/%Y/%m/',
        blank=True,
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDENTE,
    )

    destaque = models.BooleanField(
        default=False,
        help_text='Exibir o pet em destaque na página inicial.',
    )

    motivo_rejeicao = models.TextField(
        'motivo da rejeição',
        blank=True,
    )

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pets_cadastrados',
    )

    moderado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pets_moderados',
    )

    moderado_em = models.DateTimeField(null=True, blank=True)
    publicado_em = models.DateTimeField(null=True, blank=True)
    adotado_em = models.DateTimeField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'pet'
        verbose_name_plural = 'pets'

    def __str__(self):
        return self.nome

    @property
    def idade_formatada(self):
        partes = []

        if self.idade_anos:
            texto = 'ano' if self.idade_anos == 1 else 'anos'
            partes.append(f'{self.idade_anos} {texto}')

        if self.idade_meses:
            texto = 'mês' if self.idade_meses == 1 else 'meses'
            partes.append(f'{self.idade_meses} {texto}')

        return ' e '.join(partes) or 'Idade não informada'


class FotoPet(models.Model):
    pet = models.ForeignKey(
        Pet,
        on_delete=models.CASCADE,
        related_name='fotos',
    )

    imagem = models.ImageField(
        upload_to='pets/galeria/%Y/%m/',
    )

    legenda = models.CharField(
        max_length=120,
        blank=True,
    )

    ordem = models.PositiveSmallIntegerField(default=0)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ordem', 'id']
        verbose_name = 'foto do pet'
        verbose_name_plural = 'fotos do pet'

    def __str__(self):
        return f'Foto de {self.pet.nome}'