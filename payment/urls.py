# urls.py
from django.urls import path
from .views import initialize_payment, get_user_wallet, PaystackWebhookAPIView, VerifyPaystackTransactionAPIView, stream_transaction_status

urlpatterns = [
    path("wallet/", get_user_wallet),
    path("initialize/", initialize_payment),
    path("paystack/status/", VerifyPaystackTransactionAPIView.as_view()),
    path("stream-status/", stream_transaction_status),
    path("paystack/webhook/", PaystackWebhookAPIView.as_view()),
] 