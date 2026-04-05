import uuid
import hmac
import hashlib
import json
import time
import requests
from django.db import transaction
from django.conf import settings
from django.db.models import F
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from .models import Wallet, Transaction
from .serializers import InitializePaymentSerializer, WalletSerializer, TransactionSerializer
from payment.PaystackUtils import handle_paystack, handle_successful_payment, verify_paystack_payment
from payment.FlutterwaveUtils import handle_flutterwave
from payment.StripeUtils import handle_stripe

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
            wallet = Wallet.objects.select_for_update().get(id=wallet.id)

            reference = f"tx-{uuid.uuid4().hex}"

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


class PaystackWebhookAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        paystack_signature = request.headers.get("x-paystack-signature")

        computed_signature = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode(),
            request.body,
            hashlib.sha512
        ).hexdigest()

        if computed_signature != paystack_signature:
            return Response(
                {"error": "Invalid signature"},
                status=status.HTTP_400_BAD_REQUEST
            )

        event = request.data.get("event")

        if event == "charge.success":
            handle_successful_payment(request.data)

        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class VerifyPaystackTransactionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        reference = request.GET.get('reference')
        if not reference:
            return Response({"error": "Reference required"}, status=status.HTTP_400_BAD_REQUEST)

        # Use the utility for verification
        status_msg = verify_paystack_payment(reference)
        
        if status_msg == "success":
            return Response(
                {
                    "message": "Payment verified and wallet credited",
                    "status": "success"
                },
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"error": "Verification failed or payment pending", "status": status_msg},
                status=status.HTTP_400_BAD_REQUEST
            )


def stream_transaction_status(request):
    """
    Server-Sent Events (SSE) endpoint to stream transaction status updates.
    Standard Django view (not DRF) to avoid 406 Not Acceptable errors with EventSource.
    """
    reference = request.GET.get('reference')
    if not reference:
        return HttpResponse("Reference required", status=400)

    def event_stream():
        print(f"Starting SSE stream for reference: {reference}")
        for i in range(120): # Max 4 minutes
            try:
                # Every 3 iterations (approx 6 seconds), we do an active verify call
                if i % 3 == 0:
                    status_msg = verify_paystack_payment(reference)
                    print(f"SSE Active Verify ({reference}): {status_msg}")
                    if status_msg == "success":
                        yield f"data: success\n\n"
                        return
                    elif status_msg in ["failed", "reversed"]:
                        yield f"data: {status_msg}\n\n"
                        return

                # Otherwise check local DB
                txn = Transaction.objects.filter(reference=reference).first()
                if txn and txn.status == "success":
                    yield f"data: success\n\n"
                    return
                elif txn and txn.status in ["failed", "reversed"]:
                    yield f"data: {txn.status}\n\n"
                    return
                
                # Keep the connection alive
                yield f"data: pending\n\n"
                time.sleep(2)
            except Exception as e:
                print(f"SSE Error ({reference}): {e}")
                yield "data: error\n\n"
                return

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
