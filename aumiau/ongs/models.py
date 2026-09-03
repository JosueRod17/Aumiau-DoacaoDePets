from django.db import models


class Ong(models.Model):
    nome = models.CharField(max_length=120)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)
    descricao = models.TextField(blank=True)
    aprovada = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'ONG'
        verbose_name_plural = 'ONGs'

    def __str__(self):
        return self.nome