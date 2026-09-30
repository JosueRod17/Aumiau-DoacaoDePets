from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .permissions import GRUPO_SUPERVISORES


PERMISSOES_SUPERVISOR = (
    ('adocoes', 'view_chamadoajuda'),
    ('adocoes', 'change_chamadoajuda'),
    ('pets', 'view_pet'),
    ('pets', 'add_pet'),
    ('pets', 'change_pet'),
    ('pets', 'view_fotopet'),
    ('ongs', 'view_ong'),
    ('ongs', 'add_ong'),
    ('ongs', 'change_ong'),
    ('auth', 'view_user'),
    ('usuarios', 'view_perfil'),
    ('supervisores', 'view_registroatividade'),
    ('supervisores', 'moderar_pet'),
    ('supervisores', 'moderar_ong'),
    ('supervisores', 'gerenciar_usuarios'),
)


@receiver(
    post_migrate,
    dispatch_uid='supervisores.configurar_grupo',
)
def configurar_grupo_supervisores(**kwargs):
    grupo, _ = Group.objects.get_or_create(
        name=GRUPO_SUPERVISORES,
    )

    permissoes = Permission.objects.none()

    for app_label, codename in PERMISSOES_SUPERVISOR:
        permissoes = permissoes | Permission.objects.filter(
            content_type__app_label=app_label,
            codename=codename,
        )

    grupo.permissions.set(permissoes.distinct())
