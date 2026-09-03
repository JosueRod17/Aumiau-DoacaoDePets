from django.db import models

class Pet(models.Model):
    class Especie(models.TextChoices):
        CACHORRO = 'cachorro', 'Cachorro'
        GATO = 'gato', 'Gato'
        OUTRO = 'outro', 'Outro'

    nome = models.CharField(max_length=80)

    especie = models.CharField(
        max_length=10,
        choices=Especie.choices,
    )

    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)
    disponivel = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']

    def __str__(self):
        return self.nome