from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from supervisores.permissions import GRUPO_SUPERVISORES


class Command(BaseCommand):
    help = 'Adiciona ou remove um usuário do grupo de Supervisores.'

    def add_arguments(self, parser):
        parser.add_argument(
            'identificador',
            help='Nome de usuário ou e-mail da conta.',
        )
        parser.add_argument(
            '--remover',
            action='store_true',
            help='Remove o acesso de supervisor.',
        )

    def handle(self, *args, **options):
        identificador = options['identificador'].strip()
        Usuario = get_user_model()

        usuario = (
            Usuario.objects
            .filter(
                Q(username__iexact=identificador)
                | Q(email__iexact=identificador)
            )
            .first()
        )

        if not usuario:
            raise CommandError(
                f'Nenhum usuário encontrado para "{identificador}".'
            )

        grupo, _ = Group.objects.get_or_create(
            name=GRUPO_SUPERVISORES,
        )

        if options['remover']:
            usuario.groups.remove(grupo)
            self.stdout.write(
                self.style.WARNING(
                    f'{usuario.get_username()} não é mais supervisor.'
                )
            )
            return

        usuario.groups.add(grupo)

        if usuario.is_staff and not usuario.is_superuser:
            usuario.is_staff = False
            usuario.save(update_fields=['is_staff'])

        self.stdout.write(
            self.style.SUCCESS(
                f'{usuario.get_username()} agora é supervisor.'
            )
        )
