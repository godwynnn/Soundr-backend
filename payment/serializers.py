# serializers.py
from rest_framework import serializers
from .models import Wallet, Transaction

class InitializePaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1)
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
            "id", "user", "balance", "currency", "hype_points", "support_points",
            "is_active", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "user", "balance", "currency", "hype_points", "support_points", "created_at", "updated_at"]


class PurchasePointsSerializer(serializers.Serializer):
    points = serializers.IntegerField(min_value=1)
    point_type = serializers.ChoiceField(choices=["support", "hype"])

    def validate(self, data):
        points = data.get('points')
        point_type = data.get('point_type')
        
        # 1 Support Point = 200, 1 Hype Point = 100
        # User specified 200 for support and 100 for hype.
        rate = 200 if point_type == "support" else 100
        total_cost = points * rate
        
        if total_cost < 1000:
            raise serializers.ValidationError(f"Minimum purchase amount is ₦1,000.00. Current total for {points} {point_type} points is ₦{total_cost}.")
            
        data['total_cost'] = total_cost
        return data

class ConvertPointsSerializer(serializers.Serializer):
    points = serializers.IntegerField(min_value=1)
    
    def validate_points(self, value):
        # We'll check the wallet balance in the view, but let's ensure it's a valid integer
        return value
