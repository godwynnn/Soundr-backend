from django.urls import path
from .views import kyc_status, submit_kyc

urlpatterns = [
    path('status/', kyc_status, name='kyc_status'),
    path('submit/', submit_kyc, name='submit_kyc'),
]
