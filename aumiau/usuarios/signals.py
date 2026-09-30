from django.conf import settings
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import DocumentoBloqueado, Perfil


@receiver(pre_delete, sender=settings.AUTH_USER_MODEL)
def preservar_bloqueio_de_documento(sender, instance, **kwargs):
    perfil = Perfil.objects.filter(usuario=instance, situacao=Perfil.Situacao.BANIDA).first()
    if perfil and perfil.cpf_hash:
        DocumentoBloqueado.objects.get_or_create(cpf_hash=perfil.cpf_hash)
