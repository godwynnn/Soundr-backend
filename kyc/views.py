from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from .models import KYCVerification
from .serializers import KYCStatusSerializer, KYCVerificationSerializer
from core.cloudinary_utils import upload_to_cloudinary
import json

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def kyc_status(request):
    """
    Returns the current KYC status of the authenticated user.
    """
    try:
        kyc = KYCVerification.objects.get(user=request.user)
        serializer = KYCStatusSerializer(kyc)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except KYCVerification.DoesNotExist:
        return Response({"status": "none", "rejection_reason": ""}, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def submit_kyc(request):
    """
    Submit KYC information including file uploads for government ID and selfie.
    """
    user = request.user
    
    # if not hasattr(user, 'is_creator') or not user.is_creator:
    #     return Response({"error": "Only creators can submit KYC documentation."}, status=status.HTTP_403_FORBIDDEN)

    # Check if a pending or approved KYC already exists
    try:
        kyc = KYCVerification.objects.get(user=user)
        if kyc.status in ['pending', 'approved']:
            return Response({"error": f"KYC is already {kyc.status}."}, status=status.HTTP_400_BAD_REQUEST)
    except KYCVerification.DoesNotExist:
        kyc = None

    data = request.data
    
    required_fields = ['fullName', 'dob', 'address']
    for field in required_fields:
        if field not in data:
            return Response({"error": f"Missing required field: {field}"}, status=status.HTTP_400_BAD_REQUEST)

    gov_id_file = request.FILES.get('governmentId')
    selfie_file = request.FILES.get('selfie')

    if not gov_id_file or not selfie_file:
        return Response({"error": "Both Government ID and Selfie files are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Upload files to Cloudinary
        gov_upload = upload_to_cloudinary(gov_id_file, resource_type='auto', folder='soundr/kyc/ids')
        selfie_upload = upload_to_cloudinary(selfie_file, resource_type='image', folder='soundr/kyc/selfies')


        gov_url = gov_upload.get('url')
        selfie_url = selfie_upload.get('url')

        if not gov_url or not selfie_url:
            raise Exception("Failed to retrieve secure URLs from Cloudinary.")

    except Exception as e:
        return Response({'error': f'Cloudinary upload failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Update or create KYC Verification record
    if kyc:
        kyc.full_name = data['fullName']
        kyc.date_of_birth = data['dob']
        kyc.address = data['address']
        kyc.government_id_url = gov_url
        kyc.face_verification_url = selfie_url
        kyc.status = 'pending'
        kyc.rejection_reason = ''
        kyc.save()
    else:
        kyc = KYCVerification.objects.create(
            user=user,
            full_name=data['fullName'],
            date_of_birth=data['dob'],
            address=data['address'],
            government_id_url=gov_url,
            face_verification_url=selfie_url,
            status='pending'
        )

    return Response({
        "message": "KYC submitted successfully and is pending review.",
        "status": "pending"
    }, status=status.HTTP_201_CREATED)
