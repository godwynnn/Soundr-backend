from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    followers_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'display_name', 'bio', 'avatar_url', 'is_creator', 'followers_count']

    def get_followers_count(self, obj):
        # Calculate followers from the listener app's FollowedArtist model
        return obj.followers.count()

class PublicUserSerializer(serializers.ModelSerializer):
    followers_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'display_name', 'bio', 'avatar_url', 'is_creator', 'followers_count', 'is_following']

    def get_followers_count(self, obj):
        return obj.followers.count()

    def get_is_following(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Avoid circular import by importing here if necessary, 
            # though User model usually knows its followers if defined.
            from listener.models import FollowedArtist
            return FollowedArtist.objects.filter(user=request.user, artist=obj).exists()
        return False

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['username'] = user.username
        token['email'] = user.email
        return token
