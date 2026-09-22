"""
Configuracao do projeto RJ360.

Le variaveis de ambiente de um arquivo .env (veja .env.example).
"""
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key-trocar-em-producao")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.humanize",
    "django.contrib.staticfiles",
    # terceiros
    "widget_tweaks",
    # locais
    "apps.core",
    "apps.accounts",
    "apps.empresas",
    "apps.processos",
    "apps.crm",
    "apps.portal",
    "apps.integracoes",
    "apps.notificacoes",
    "apps.publico",
    "apps.relacionamento",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.branding",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": dj_database_url.parse(
        os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
    )
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = os.getenv("TIME_ZONE", "America/Sao_Paulo")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# O manifesto so existe depois do collectstatic, entao ele e opcional: ligue
# DJANGO_STATIC_MANIFEST=True no servidor, onde o collectstatic roda no deploy.
_ESTATICOS = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
    if env_bool("DJANGO_STATIC_MANIFEST", False)
    else "whitenoise.storage.CompressedStaticFilesStorage"
)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": _ESTATICOS},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "accounts:login"

MESSAGE_TAGS = {
    10: "debug",
    20: "info",
    25: "success",
    30: "warning",
    40: "error",
}

# Prazos: quantos dias antes do vencimento um prazo entra no alerta do painel.
PRAZO_ALERTA_DIAS = int(os.getenv("PRAZO_ALERTA_DIAS", "15"))

# Endereco publico do sistema, usado nos links dos e-mails.
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")

# E-mail. Sem SMTP configurado, as mensagens saem no terminal (util em dev).
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "20"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "RJ360 <nao-responda@localhost>")
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend",
)

# Quem recebe os avisos de prazos sem responsavel definido.
NOTIFICACOES_SUPERVISAO = env_list("NOTIFICACOES_SUPERVISAO")

# Como o codigo de acesso do portal e enviado: "email" (padrao) ou "nenhum"
# enquanto um canal de WhatsApp nao estiver contratado.
CANAL_CODIGO_ACESSO = os.getenv("CANAL_CODIGO_ACESSO", "email")

# Numero de WhatsApp da consultoria, so digitos com DDI (ex.: 5519999998888).
WHATSAPP_NUMERO = os.getenv("WHATSAPP_NUMERO", "").strip()

# Integracao com a API publica do DataJud (CNJ).
# A chave e publica, mas fica no .env: https://datajud-wiki.cnj.jus.br/api-publica/acesso/
DATAJUD_API_KEY = os.getenv("DATAJUD_API_KEY", "")
DATAJUD_BASE_URL = os.getenv("DATAJUD_BASE_URL", "https://api-publica.datajud.cnj.jus.br")
DATAJUD_AUTH_SCHEME = os.getenv("DATAJUD_AUTH_SCHEME", "APIKey")
DATAJUD_TIMEOUT = int(os.getenv("DATAJUD_TIMEOUT", "30"))
# Andamentos importados do tribunal ficam restritos a equipe ate serem liberados.
DATAJUD_ANDAMENTOS_VISIVEIS_CLIENTE = env_bool("DATAJUD_ANDAMENTOS_VISIVEIS_CLIENTE", False)

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
