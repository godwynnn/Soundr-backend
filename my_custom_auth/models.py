from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    # Enforce email for authentication
    email = models.EmailField(unique=True)
    is_creator = models.BooleanField(default=False)
    
    # Profile fields
    display_name = models.CharField(max_length=255, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True, null=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
