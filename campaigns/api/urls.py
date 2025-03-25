from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SenderIdViewSet, ContactViewSet, SMSAPIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

router = DefaultRouter()
router.register(r'senderids', SenderIdViewSet, basename='sender-id')
router.register(r'contacts', ContactViewSet, basename='contact')

urlpatterns = [
    path('', include(router.urls)),
    path('send-sms/', SMSAPIView.as_view(), name='send-sms'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
