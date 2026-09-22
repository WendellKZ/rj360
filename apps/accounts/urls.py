from django.contrib.auth import views as auth_views
from django.urls import path

app_name = "accounts"

urlpatterns = [
    path(
        "entrar/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "senha/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change.html",
            success_url="/conta/senha/ok/",
        ),
        name="password_change",
    ),
    path(
        "senha/ok/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/password_change_done.html"
        ),
        name="password_change_done",
    ),
]
