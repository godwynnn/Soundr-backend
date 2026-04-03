import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from oauth2_provider.models import Application
from my_custom_auth.models import CustomUser

try:
    user = CustomUser.objects.get(username='a')
    app, created = Application.objects.get_or_create(
        name='Soundr SPA',
        defaults={
            'user': user,
            'client_type': 'public',
            'authorization_grant_type': 'password',
        }
    )
    with open('oauth_creds.txt', 'w') as f:
        f.write(f"CLIENT_ID={app.client_id}\n")
        f.write(f"CLIENT_SECRET={app.client_secret}\n")
    print("SUCCESS: Credentials saved to oauth_creds.txt")
except Exception as e:
    print(f"ERROR: {e}")
