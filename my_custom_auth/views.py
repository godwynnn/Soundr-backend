from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import MyTokenObtainPairSerializer
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from core.cloudinary_utils import upload_to_cloudinary
import requests as django_requests
from django.conf import settings
from django.contrib.auth import login, authenticate
from social_django.utils import psa
from django.shortcuts import get_object_or_404
from .serializers import UserSerializer, PublicUserSerializer, WaitlistSerializer
from .models import Waitlist
# For Google ID token verification
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_auth_requests


User = get_user_model()

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    email = request.data.get('email')
    password = request.data.get('password')

    if not email or not password:
        return Response({'error': 'Please provide both email and password.'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.get(email=email)
    
    # Check if user exists
    if not user:
        return Response({'error': 'Invalid Email or password'}, status=status.HTTP_401_UNAUTHORIZED)
    
    # Check if user is active
    if not user.is_active:
        return Response({'error': 'Account deactivated'}, status=status.HTTP_401_UNAUTHORIZED)
    
    # Check if user has a usable password (signed up via social but never set one)
    if not user.has_usable_password():
        return Response({'error': 'This email is associated with a social account. Please use Google Login.'}, status=status.HTTP_401_UNAUTHORIZED)

  
    # Authenticate
    # user = authenticate(request,username=user.email, password=password)
    
    if user.check_password(password):
        tokens = get_tokens_for_user(user)
        return Response({
            'status': 'success',
            'access': str(tokens['access']),
            'refresh': str(tokens['refresh']),
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)
    else:
        return Response({'error': 'Invalid Email or password'}, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
@permission_classes([AllowAny])
def signup_view(request):
    email = request.data.get('email')
    password = request.data.get('password')
    username = request.data.get('username')

    if not email or not password or not username:
        return Response({'error': 'Please provide all required fields.'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(email=email).exists():
        return Response({'error': 'Email already in use.'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, email=email, password=password)
    
    refresh = RefreshToken.for_user(user)
    
    return Response({
        'message': 'User created successfully.',
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': {'email': user.email, 'username': user.username, 'id': user.id}
    }, status=status.HTTP_201_CREATED)


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

def verify_google_id_token(token):
    try:
        # We need the Google Client ID from settings
        client_id = getattr(settings, 'SOCIAL_AUTH_GOOGLE_OAUTH2_KEY', None)
        idinfo = google_id_token.verify_oauth2_token(
            token, google_auth_requests.Request(), client_id
        )
        return idinfo
    except Exception:
        return None

@api_view(["POST"])
@permission_classes([AllowAny])
@psa()
def VerifySocialLogin(request, backend):
    access_token = request.data.get("access_token")
    id_token = request.data.get("id_token")

    if access_token:
        token = access_token
        social_user = request.backend.do_auth(token)

        if not social_user:
            return Response(
                {"status": "failed", "error": "Invalid social token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # THIS is the Django user
        user = User.objects.get(email=social_user.email)

    elif id_token:
        idinfo = verify_google_id_token(id_token)
        if not idinfo:
            return Response(
                {"status": "failed", "error": "Invalid ID token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        email = idinfo.get("email")
        first_name = idinfo.get("given_name", "")
        last_name = idinfo.get("family_name", "")

        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                "username": str(email).split('@')[0],
                "first_name": first_name,
                "last_name": last_name
            },
        )

    else:
        return Response(
            {"status": "failed", "error": "No token provided"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Explicitly activate
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
    
        #  SESSION AUTH (NO authenticate())
        login(
            request,
            user,
            backend="django.contrib.auth.backends.ModelBackend",
        )

        #  JWT TOKENS
        tokens = get_tokens_for_user(user)

        response = Response(
            {
                "status": "success",
                "tokens": {
                    "access_token": str(tokens["access"]),
                    "refresh_token": str(tokens["refresh"]),
                },
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )

        return response
    
    except Exception as e:
        return Response(
            {"status": "failed", "error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )

@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({'message': 'Successfully logged out.'}, status=status.HTTP_200_OK)
    except Exception:
        return Response({'message': 'Logged out.'}, status=status.HTTP_200_OK)

@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """
    GET: Return serialized user data.
    PATCH: Update user details (display_name, bio, avatar).
    """
    user = request.user
    
    if request.method == 'PATCH':
        display_name = request.data.get('display_name')
        bio = request.data.get('bio')
        avatar_file = request.FILES.get('avatar')
        
        if display_name is not None:
            user.display_name = display_name
        if bio is not None:
            user.bio = bio
            
        if avatar_file:
            try:
                upload_res = upload_to_cloudinary(avatar_file, folder='avatars')
                user.avatar_url = upload_res.get('url')
            except Exception as e:
                return Response({'error': f'Avatar upload failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        user.save()
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    # GET request
    serializer = UserSerializer(user)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([AllowAny])
def public_profile_view(request, user_id):
    """
    Returns public profile data for any user by their ID.
    Excludes sensitive information like email and wallet data.
    """
    user = get_object_or_404(User, id=user_id)
    serializer = PublicUserSerializer(user, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
def join_waitlist(request):
    serializer = WaitlistSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def trigger_error(request):
    division_by_zero = 1 / 1

    return Response({'value':division_by_zero})