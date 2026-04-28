from rest_framework import serializers
from .models import KYCVerification

class KYCVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCVerification
        fields = [
            'id', 'user', 'full_name', 'date_of_birth', 'address',
            'government_id_url', 'face_verification_url', 'status',
            'rejection_reason', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'status', 'rejection_reason', 'created_at', 'updated_at']

class KYCStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCVerification
        fields = ['status', 'rejection_reason']
