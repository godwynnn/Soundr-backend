from django.contrib import admin
from django.urls import path, include
from my_custom_auth.views import signup_view, logout_view, VerifySocialLogin, profile_view
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/listener/', include('listener.urls')),
    path('api/creator/', include('creator.urls')),
    path('api/payment/', include('payment.urls')),
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/signup/', signup_view, name='auth-signup'),
    path('api/auth/logout/', logout_view, name='auth-logout'),
    path('api/auth/social/<str:backend>/', VerifySocialLogin, name='social-login'),
    path('api/auth/profile/', profile_view, name='user-profile'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/', include('drf_social_oauth2.urls', namespace='drf')),
]
