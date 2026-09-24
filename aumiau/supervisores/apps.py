from django.apps import AppConfig


class SupervisoresConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'supervisores'
    verbose_name = 'Supervisores'

    def ready(self):
        from . import signals  # noqa: F401
