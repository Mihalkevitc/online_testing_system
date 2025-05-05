from django.apps import AppConfig


class TestingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'testing'

    def ready(self):
            # Импортируем сигналы при запуске приложения
            import testing.signals