from django.urls import path

from trips import views

urlpatterns = [
    # Full addresses: /api/health, /api/geocode, /api/plan
    path("health", views.health),
    path("geocode", views.geocode),
    path("plan", views.plan),
    path("corridor-forecast", views.corridor_forecast),
]
