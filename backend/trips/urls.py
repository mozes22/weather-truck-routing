from django.urls import path

from trips import views

urlpatterns = [
    # Full address: /api/health
    path("health", views.health),
]
