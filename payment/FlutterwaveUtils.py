import requests
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status


def handle_flutterwave(email, amount, reference):
    url = "https://api.flutterwave.com/v3/payments"

    headers = {
        "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "tx_ref": reference,
        "amount": str(amount),
        "currency": "NGN",
        "redirect_url": "https://yourdomain.com/payment/callback/",
        "customer": {
            "email": email,
        },
    }

    response = requests.post(url, json=data, headers=headers)
    return Response(response.json(), status=response.status_code)