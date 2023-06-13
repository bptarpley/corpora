from django.conf import settings


class PluginModelRouter:

    def db_for_read(self, model, **hints):
        db_name = f'plugins.{model._meta.app_label}'
        if db_name in settings.DATABASES:
            return db_name
        return None

    def db_for_write(self, model, **hints):
        db_name = f'plugins.{model._meta.app_label}'
        if db_name in settings.DATABASES:
            return db_name
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        db_name = f'plugins.{app_label}'
        if db_name in settings.DATABASES:
            return db_name == db
        else:
            return db == 'default'
