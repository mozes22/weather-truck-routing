from django.urls import include, path

urlpatterns = [
    # Every address starting with /api/ is handled by the trips app.
    path("api/", include("trips.urls")),
]
