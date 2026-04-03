from django.apps import AppConfig

class AuthAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'my_custom_auth'
    # Use a custom label to prevent completely colliding with django.contrib.auth
    label = 'my_custom_auth'
