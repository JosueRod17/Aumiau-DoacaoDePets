from django.contrib.admin.apps import AdminConfig


class AuMiauAdminConfig(AdminConfig):
    default_site = 'aumiau.admin_site.AuMiauAdminSite'