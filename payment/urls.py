# urls.py
from django.urls import path
from .views import initialize_payment, get_user_wallet, PaystackWebhookAPIView, VerifyPaystackTransactionAPIView, stream_transaction_status, purchase_points
from .views import initialize_payment, get_user_wallet, PaystackWebhookAPIView, VerifyPaystackTransactionAPIView, stream_transaction_status, purchase_points, support_song
from . import views

urlpatterns = [
    path("wallet/", get_user_wallet),
    path("initialize/", initialize_payment),
    path("paystack/status/", VerifyPaystackTransactionAPIView.as_view()),
    path("stream-status/", stream_transaction_status),
    path('purchase-points/', views.purchase_points, name='purchase-points'),
    path('support-song/<int:song_id>/', views.support_song, name='support-song'),
    path("paystack/webhook/", PaystackWebhookAPIView.as_view()),
]