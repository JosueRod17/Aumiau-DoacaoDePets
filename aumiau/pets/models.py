from django.conf import settings
from django.core.validators import MaxValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from usuarios.models import UF_CHOICES


class PetQuerySet(models.QuerySet):
    def publicos(self):
        return self.filter(status='publicado').filter(
            Q(ong__isnull=True) | Q(ong__status='aprovada')
        )

    def gerenciaveis_por(self, usuario):
        if not usuario.is_authenticated:
            return self.none()
        return self.filter(
            Q(ong__isnull=True, responsavel=usuario)
            | Q(ong__isnull=True, responsavel__isnull=True, criado_por=usuario)
            | Q(ong__responsavel=usuario)
        ).distinct()


class Pet(models.Model):
    objects = PetQuerySet.as_manager()

    class Especie(models.TextChoices):
        CACHORRO = 'cachorro', 'Cachorro'
        GATO = 'gato', 'Gato'
        COELHO = 'coelho', 'Coelho'
        HAMSTER = 'hamster', 'Hamster'
        PORQUINHO_DA_INDIA = 'porquinho_da_india', 'Porquinho-da-índia'
        AVE = 'ave', 'Ave'
        PEIXE = 'peixe', 'Peixe'
        TARTARUGA = 'tartaruga', 'Tartaruga / jabuti'
        FURAO = 'furao', 'Furão'
        CHINCHILA = 'chinchila', 'Chinchila'
        REPTIL = 'reptil', 'Outro réptil'
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
        RASCUNHO = 'rascunho', 'Rascunho'
        PENDENTE = 'pendente', 'Em análise'
        PUBLICADO = 'publicado', 'Publicado'
        ADOTADO = 'adotado', 'Adotado'
        REJEITADO = 'rejeitado', 'Rejeitado'
        ARQUIVADO = 'arquivado', 'Arquivado'

    nome = models.CharField(max_length=80)
    codigo_demonstracao = models.CharField(max_length=40, unique=True, null=True, blank=True, editable=False)

    especie = models.CharField(
        max_length=20,
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

    data_nascimento = models.DateField('data de nascimento', null=True, blank=True)
    idade_estimada_informada = models.BooleanField(default=False, editable=False)

    idade_anos = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(150)],
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
    email_contato = models.EmailField('e-mail público para contato', blank=True)
    telefone_contato = models.CharField('telefone público para contato', max_length=20, blank=True)
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

    def clean(self):
        super().clean()
        if self.data_nascimento and self.data_nascimento > timezone.localdate():
            raise ValidationError({'data_nascimento': 'A data de nascimento não pode ser no futuro.'})

    @property
    def idade_atual(self):
        if not self.data_nascimento:
            return self.idade_anos, self.idade_meses
        hoje = timezone.localdate()
        meses = ((hoje.year - self.data_nascimento.year) * 12
                 + hoje.month - self.data_nascimento.month
                 - (hoje.day < self.data_nascimento.day))
        return divmod(max(meses, 0), 12)

    @property
    def idade_formatada(self):
        partes = []
        anos, meses = self.idade_atual

        if anos:
            texto = 'ano' if anos == 1 else 'anos'
            partes.append(f'{anos} {texto}')

        if meses:
            texto = 'mês' if meses == 1 else 'meses'
            partes.append(f'{meses} {texto}')

        idade = ' e '.join(partes) or ('Menos de 1 mês' if self.data_nascimento or self.idade_estimada_informada else 'Idade não informada')
        if not self.data_nascimento and self.idade_estimada_informada:
            idade += ' (aprox.)'
        return idade


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
