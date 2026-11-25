
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("api/home-summary/", views.home_summary, name="home-summary"),
    path("api/status/<int:spot_id>/", views.status_summary, name="status-summary"),
    path("api/reception/", views.reception_fragment, name="reception-fragment"),
    path("api/barber/<str:name>/", views.barber_fragment, name="barber-fragment"),
    path("api/display/", views.display_fragment, name="display-fragment"),
    path("account/register/", views.register, name="account-register"),
    path("account/login/", views.login_view, name="account-login"),
    path("account/logout/", views.logout_view, name="account-logout"),
    path("join/", views.join, name="join"),
    path("status/<str:spot_id>/", views.status, name="status"),
    path("reception/", views.reception, name="reception"),
    path("barber/<str:name>/", views.barber, name="barber"),
    path("display/", views.display, name="display"),
    path("admin/", views.owner_settings, name="owner-settings"),
]
