from django.urls import include, path

urlpatterns = [path("", include("queue_app.urls"))]
