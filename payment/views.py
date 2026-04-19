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

from .models import Wallet, Transaction, BankAccount, Beneficiary
from .serializers import (
    InitializePaymentSerializer, WalletSerializer, TransactionSerializer, 
    PurchasePointsSerializer, ConvertPointsSerializer,
    BankAccountSerializer, BeneficiarySerializer
)
from creator.models import Song
from payment.PaystackUtils import handle_paystack, handle_successful_payment, verify_paystack_payment,get_banks_paystack
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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def purchase_points(request):
    """
    Purchase Support or Hype points using the user's existing wallet balance.
    Minimum purchase value: ₦1,000.
    """
    serializer = PurchasePointsSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    points = serializer.validated_data['points']
    point_type = serializer.validated_data['point_type']
    total_cost = serializer.validated_data['total_cost']

    try:
        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(user=request.user)

            if wallet.balance < total_cost:
                return Response(
                    {"error": f"Insufficient balance. You need ₦{total_cost:,.2f} but only have ₦{wallet.balance:,.2f}."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Deduct balance
            wallet.balance = F('balance') - total_cost
            
            # Add points
            if point_type == "support":
                wallet.support_points = F('support_points') + points
                tx_type = "purchase_support"
                desc = f"Purchased {points} Support Points"
            else:
                wallet.hype_points = F('hype_points') + points
                tx_type = "purchase_hype"
                desc = f"Purchased {points} Hype Points"

            wallet.save()
            wallet.refresh_from_db()

            # Create Transaction Record
            Transaction.objects.create(
                user=request.user,
                wallet=wallet,
                amount=total_cost,
                currency="NGN",
                transaction_type=tx_type,
                payment_method="wallet",
                status="success",
                reference=f"buy-{uuid.uuid4().hex[:12]}",
                description=desc
            )

            # Prepare full response with updated wallet
            w_serializer = WalletSerializer(wallet)
            data = w_serializer.data
            
            # Include recent transactions
            transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at')[:20]
            tx_serializer = TransactionSerializer(transactions, many=True)
            data['transactions'] = tx_serializer.data

            return Response({
                "message": f"Successfully purchased {points} {point_type} points.",
                "wallet": data
            }, status=status.HTTP_200_OK)

    except Wallet.DoesNotExist:
        return Response({"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def support_song(request, song_id):
    """
    Transfer 1 support point from the current user to the song creator.
    """
    try:
        from django.db import transaction as db_transaction
        import uuid
        
        song = Song.objects.get(id=song_id)
        creator = song.uploaded_by
        
        if not creator:
            return Response({"error": "This song has no associated creator."}, status=status.HTTP_400_BAD_REQUEST)
        
        if creator == request.user:
            return Response({"error": "You cannot support your own tracks."}, status=status.HTTP_400_BAD_REQUEST)

        with db_transaction.atomic():
            # Get sender wallet
            sender_wallet = Wallet.objects.select_for_update().get(user=request.user)
            
            if sender_wallet.support_points < 1:
                return Response({"error": "Insufficient support points. Please top up your wallet."}, status=status.HTTP_400_BAD_REQUEST)
            
            # Get receiver wallet (creator)
            receiver_wallet, created = Wallet.objects.select_for_update().get_or_create(
                user=creator,
                defaults={'currency': 'NGN'}
            )
            
            # Perform transfer
            # Note: We need to use integer values, not F expressions if we want to return the result immediately easily, 
            # or just reload them.
            sender_wallet.support_points -= 1
            receiver_wallet.support_points += 1
            
            sender_wallet.save()
            receiver_wallet.save()
            
            # Create Transaction for Sender
            Transaction.objects.create(
                user=request.user,
                wallet=sender_wallet,
                amount=0,
                currency="NGN",
                transaction_type="withdrawal",
                payment_method="wallet",
                status="success",
                reference=f"sup-out-{uuid.uuid4().hex[:12]}",
                description=f"Sent 1 Support Point to {creator.username} for track: {song.title}"
            )
            
            # Create Transaction for Receiver
            Transaction.objects.create(
                user=creator,
                wallet=receiver_wallet,
                amount=0,
                currency="NGN",
                transaction_type="deposit",
                payment_method="wallet",
                status="success",
                reference=f"sup-in-{uuid.uuid4().hex[:12]}",
                description=f"Received 1 Support Point from {request.user.username} for track: {song.title}"
            )

            return Response({
                "message": f"Successfully supported {song.title}! 1 point has been sent to {creator.username}.",
                "remaining_points": sender_wallet.support_points
            }, status=status.HTTP_200_OK)

    except Song.DoesNotExist:
        return Response({"error": "Song not found"}, status=status.HTTP_404_NOT_FOUND)
    except Wallet.DoesNotExist:
        return Response({"error": "Your wallet was not found. Please contact support."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def convert_points_to_naira(request):
    """
    Convert earned support points into Naira balance in the wallet.
    Rate: 1 Support Point = ₦200.00.
    """
    serializer = ConvertPointsSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    points = serializer.validated_data['points']
    naira_equivalent = points * 200

    try:
        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(user=request.user)

            if wallet.support_points < points:
                return Response(
                    {"error": f"Insufficient support points. You have {wallet.support_points} but tried to convert {points}."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Perform conversion
            wallet.support_points = F('support_points') - points
            wallet.balance = F('balance') + naira_equivalent
            
            wallet.save()
            wallet.refresh_from_db()

            # Create Transaction Record
            Transaction.objects.create(
                user=request.user,
                wallet=wallet,
                amount=naira_equivalent,
                currency="NGN",
                transaction_type="deposit",
                payment_method="wallet",
                status="success",
                reference=f"conv-{uuid.uuid4().hex[:12]}",
                description=f"Converted {points} Support Points to Naira"
            )

            # Return updated wallet data
            w_serializer = WalletSerializer(wallet)
            data = w_serializer.data
            
            # Include recent transactions
            transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at')[:20]
            tx_serializer = TransactionSerializer(transactions, many=True)
            data['transactions'] = tx_serializer.data

            return Response({
                "message": f"Successfully converted {points} points to ₦{naira_equivalent:,.2f}.",
                "wallet": data
            }, status=status.HTTP_200_OK)

    except Wallet.DoesNotExist:
        return Response({"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_banks(request):
    data, status_code = get_banks_paystack()
    return Response(data, status=status_code)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resolve_bank_account(request):
    """
    Resolve a bank account number to get the account name.
    """
    account_number = request.data.get("account_number")
    bank_code = request.data.get("bank_code")

    if not account_number or not bank_code:
        return Response(
            {"error": "Account number and bank code are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        response = requests.get(
            f"https://api.paystack.co/bank/resolve?account_number={account_number}&bank_code={bank_code}",
            headers={
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
            }
        )
        print(response.json())

        if response.status_code != 200:
            return Response(
                {"error": "Unable to resolve account number"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        data = response.json()
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_transfer_recipient(request):
    """
    Create a transfer recipient on Paystack and save the bank account/beneficiary locally.
    """
    url = "https://api.paystack.co/transferrecipient"

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    print(request.data)
    # Data from frontend
    account_number = request.data.get("account_number")
    bank_code = request.data.get("bank_code")
    bank_name = request.data.get("bank_name", "Unknown Bank") # Passed from frontend for DB
    name = request.data.get("name") # Account Name or Nickname

    if not all([account_number, bank_code, name]):
        return Response(
            {"error": "Account number, bank code, and name are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    payload = {
        "type": "nuban",
        "name": name,
        "account_number": account_number,
        "bank_code": bank_code,
        "currency": "NGN"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        res_data = response.json()
        print(res_data)

        if response.status_code in [200, 201] and res_data.get("status"):
            recipient_data = res_data.get("data")
            recipient_code = recipient_data.get("recipient_code")

            with transaction.atomic():
                # Get or create the BankAccount
                bank_account, created = BankAccount.objects.get_or_create(
                    recipient_code=recipient_code,
                    defaults={
                        "user": request.user,
                        "account_name": name,
                        "account_number": account_number,
                        "bank_code": bank_code,
                        "bank_name": bank_name,
                        "currency": "NGN"
                    }
                )

                # Create or update the Beneficiary record
                beneficiary, b_created = Beneficiary.objects.get_or_create(
                    user=request.user,
                    bank_account=bank_account,
                    defaults={
                        "name": name
                    }
                )
                if not b_created:
                    from django.utils import timezone
                    beneficiary.last_used = timezone.now()
                    beneficiary.save()

            # Return success with the saved objects data
            return Response({
                "message": "Recipient created and saved successfully",
                "recipient_code": recipient_code,
                "bank_account": BankAccountSerializer(bank_account).data,
                "beneficiary": BeneficiarySerializer(beneficiary).data
            }, status=status.HTTP_201_CREATED)

        return Response(res_data, status=response.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"error": "Failed to create transfer recipient", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {"error": "An internal error occurred", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_beneficiaries(request):
    """
    List saved beneficiaries for the authenticated user.
    """
    beneficiaries = Beneficiary.objects.filter(user=request.user, is_active=True).order_by('-last_used')
    serializer = BeneficiarySerializer(beneficiaries, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)