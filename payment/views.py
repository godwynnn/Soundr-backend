import uuid
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Wallet, Transaction
from .serializers import InitializePaymentSerializer, WalletSerializer
from rest_framework.response import Response
from rest_framework import status
import requests
from django.conf import settings

PAYSTACK_URL = "https://api.paystack.co/transaction/initialize"

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_wallet(request):
    try:
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        serializer = WalletSerializer(wallet)
        data = serializer.data
        
        # Get recent transactions associated with the user
        transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at')[:20]
        # We can serialize them manually or with TransactionSerializer
        from .serializers import TransactionSerializer
        tx_serializer = TransactionSerializer(transactions, many=True)
        data['transactions'] = tx_serializer.data

        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def initialize_payment(request):
    serializer = InitializePaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    amount = serializer.validated_data["amount"]
    payment_method = serializer.validated_data["payment_method"]
    email = request.user.email

    if not email:
        return Response({"error": "User must have a valid email address"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            wallet, created = Wallet.objects.get_or_create(user=request.user)
            # Atomicity: Lock the wallet to prevent concurrent initialize requests for the same user
            wallet = Wallet.objects.select_for_update().get(id=wallet.id)

            # Prevent initializing duplicate exact same transactions rapidly (optional, but good practice)
            # Check if there corresponds a pending one locally created within the last few minutes.
            # But creating a new pending transaction is safer, so we just log it.

            reference = f"tx-{uuid.uuid4().hex}"

            # Log standard Transaction object before calling third parties!
            tx = Transaction.objects.create(
                user=request.user,
                wallet=wallet,
                amount=amount,
                currency="NGN",
                transaction_type="deposit",
                payment_method=payment_method,
                status="pending",
                reference=reference,
                description=f"Wallet Funding via {payment_method.capitalize()}"
            )

            # Call specific payment gateways
            if payment_method == "paystack":
                return handle_paystack(email, amount, reference)
            elif payment_method == "flutterwave":
                return handle_flutterwave(email, amount, reference)
            elif payment_method == "stripe":
                return handle_stripe(email, amount, reference)

    except Wallet.DoesNotExist:
        return Response({"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
