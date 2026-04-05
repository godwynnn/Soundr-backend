import requests
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status
import json
from django.db.models import F
from .models import Wallet, Transaction
from django.db import transaction


PAYSTACK_URL = "https://api.paystack.co/transaction/initialize"

def handle_paystack(email, amount, reference):
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "email": email,
        "amount": int(float(amount) * 100),  # amount in kobo
        "reference": reference,
        "channels": ["card", "bank", "ussd", "qr", "mobile_money", "bank_transfer"]
    }

    response = requests.post(PAYSTACK_URL, json=data, headers=headers)
    
    if response.status_code == 200:
        return Response(response.json(), status=status.HTTP_200_OK)
    else:
        return Response(response.json(), status=response.status_code)





def handle_successful_payment(payload):
        data = payload.get("data", {})

        reference = data.get("reference")
        amount = data.get("amount", 0) / 100  # kobo → naira

    
        try:

            with transaction.atomic():

                # 🔁 Lock transaction for idempotency
                txn = Transaction.objects.select_for_update().filter(
                    reference=reference
                ).first()

                if not txn:
                    return

                if txn.status == "success":
                    return  # already processed

                # ✅ Update transaction
                txn.status = "success"
                txn.external_reference = data.get("id")
                txn.save()

                # 🔒 Lock wallet + atomic update
                wallet = Wallet.objects.select_for_update().get(user=txn.user)

                Wallet.objects.filter(pk=wallet.pk).update(
                    balance=F("balance") + amount
                )

        except Exception as e:
            # log error (important in production)
            print("Webhook error:", str(e))


def verify_paystack_payment(reference):
    """
    Actively verify a transaction with Paystack and update the local DB.
    """
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return "pending"
            
        data = response.json()
        if not data.get("status"):
            return "pending"

        payment_data = data.get("data", {})
        if payment_data.get("status") == "success":
            # Reuse the webhook logic to update DB and credit wallet
            handle_successful_payment({"data": payment_data})
            return "success"
        
        return payment_data.get("status", "pending")
    except Exception as e:
        print(f"Verification error for {reference}: {e}")
        return "error"
