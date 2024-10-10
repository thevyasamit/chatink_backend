from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import *


router = DefaultRouter()
router.register(r'users', UsersView, basename='users')
router.register(r'links',UserLinksView, basename='user_links')
router.register(r'context',UserContextView,basename='user_context')


urlpatterns = [
    path('', include(router.urls)),
]
