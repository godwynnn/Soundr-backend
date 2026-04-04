# serializers.py
from rest_framework import serializers
from .models import Wallet, Transaction

class InitializePaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1.00)
    payment_method = serializers.ChoiceField(choices=["paystack", "flutterwave", "stripe"])


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id", "user", "wallet", "amount", "currency", "transaction_type",
            "payment_method", "status", "reference", "external_reference",
            "description", "metadata", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "user", "wallet", "reference", "created_at", "updated_at"]


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = [
            "id", "user", "balance", "currency", "is_active", 
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "user", "balance", "currency", "created_at", "updated_at"]
