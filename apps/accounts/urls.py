"""URL routing for accounts module."""

from django.urls import path

from apps.accounts.views import UserLoginView, UserLogoutView, UserProfileView

app_name = "accounts"

urlpatterns = [
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("profile/", UserProfileView.as_view(), name="profile"),
]
