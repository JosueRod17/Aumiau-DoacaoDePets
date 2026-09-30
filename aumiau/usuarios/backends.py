from django.contrib.auth.backends import ModelBackend

from .models import Perfil


class ContaBackend(ModelBackend):
    def user_can_authenticate(self, user):
        return super().user_can_authenticate(user) and not Perfil.objects.filter(
            usuario=user, situacao__in=[Perfil.Situacao.SUSPENSA, Perfil.Situacao.BANIDA, Perfil.Situacao.EXCLUIDA],
        ).exists()
