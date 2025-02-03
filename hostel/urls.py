
from django.urls import path, include
from django.contrib import admin
from . import views
from rest_framework.routers import DefaultRouter

from .views import StatisticsViewSet

router = DefaultRouter()
router.register('rental-posts', views.RentalPostViewSet)
router.register('tenant-requests', views.TenantRequestViewSet)
router.register('users', views.UserViewSet)
router.register('images', views.ImageViewSet)
router.register('cities', views.CityViewSet)
router.register('wards', views.WardViewSet)
router.register('districts', views.DistrictViewSet)
router.register('follows', views.FollowViewSet)
router.register('statistics', StatisticsViewSet, basename='statistics')  # Thêm basename



urlpatterns = [
    path('', include(router.urls)),

]

