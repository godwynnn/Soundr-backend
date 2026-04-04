# urls.py
from django.urls import path
from .views import initialize_payment, get_user_wallet

urlpatterns = [
    path("wallet/", get_user_wallet),
    path("initialize/", initialize_payment),
]