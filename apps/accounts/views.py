"""Accounts views for Authentication and Profile Management."""

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views import View

from apps.accounts.forms import LoginForm, UserProfileForm
from apps.accounts.services import UserService
from apps.audit.services import AuditService


class UserLoginView(LoginView):
    """B2B Login view using custom styled form."""

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form: LoginForm) -> HttpResponse:
        response = super().form_valid(form)
        AuditService.log(
            action="USER_LOGIN",
            user=self.request.user,
            resource_type="User",
            resource_id=str(self.request.user.id),
            details={"username": self.request.user.username},
            ip_address=self.request.META.get("REMOTE_ADDR"),
        )
        messages.success(self.request, f"Welcome back, {self.request.user.username}!")
        return response


class UserLogoutView(View):
    """Handles logout for both POST and GET safely."""

    def post(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            AuditService.log(
                action="USER_LOGOUT",
                user=request.user,
                resource_type="User",
                resource_id=str(request.user.id),
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            logout(request)
        messages.info(request, "You have been safely logged out.")
        return redirect("accounts:login")

    def get(self, request: HttpRequest) -> HttpResponse:
        return self.post(request)


class UserProfileView(LoginRequiredMixin, View):
    """Allows authenticated users to view and update their profile."""

    def get(self, request: HttpRequest) -> HttpResponse:
        form = UserProfileForm(instance=request.user)
        return render(
            request,
            "accounts/profile.html",
            {
                "title": "My Profile",
                "form": form,
                "active_nav": "profile",
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            UserService.update_profile(
                user=request.user,
                first_name=form.cleaned_data.get("first_name"),
                last_name=form.cleaned_data.get("last_name"),
                email=form.cleaned_data.get("email"),
                job_title=form.cleaned_data.get("job_title"),
                phone=form.cleaned_data.get("phone"),
            )
            AuditService.log(
                action="PROFILE_UPDATED",
                user=request.user,
                resource_type="User",
                resource_id=str(request.user.id),
                details={"updated_fields": list(form.changed_data)},
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            messages.success(request, "Your profile has been updated successfully.")
            return redirect("accounts:profile")

        return render(
            request,
            "accounts/profile.html",
            {
                "title": "My Profile",
                "form": form,
                "active_nav": "profile",
            },
        )
