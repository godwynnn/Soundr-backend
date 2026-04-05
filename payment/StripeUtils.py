import requests
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status


def handle_stripe(email, amount, reference):
    url = "https://api.stripe.com/v1/payment_intents"

    headers = {
        "Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}",
    }

    data = {
        "amount": int(float(amount) * 100),
        "currency": "usd",
        "receipt_email": email,
        "metadata[reference]": reference
    }

    response = requests.post(url, data=data, headers=headers)
    return Response(response.json(), status=response.status_code)