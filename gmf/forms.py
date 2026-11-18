from django import forms
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm
from django.db import transaction

from .models import Cliente, RolUsuario, Usuario


class IngresoForm(AuthenticationForm):
    """Login con email (Usuario.USERNAME_FIELD = 'email')."""

    error_messages = {
        "invalid_login": "El correo o la contraseña no son correctos.",
        "inactive": "Esta cuenta está desactivada.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Correo"
        self.fields["username"].widget = forms.EmailInput(
            attrs={"autocomplete": "email", "autofocus": True, "placeholder": "tu@correo.com"}
        )
        self.fields["password"].label = "Contraseña"
        self.fields["password"].widget.attrs["placeholder"] = "Tu contraseña"


class RegistroForm(BaseUserCreationForm):
    """Registro de clientes: crea el Usuario (rol CLIENTE) y su perfil Cliente."""

    class Meta:
        model = Usuario
        fields = ("first_name", "last_name", "email")
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "Correo",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name", "autofocus": True}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "tu@correo.com"}),
        }
        error_messages = {
            "email": {"unique": "Ya existe una cuenta con este correo."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # En el modelo nombre y apellido son opcionales (AbstractUser); en el registro no
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["password1"].label = "Contraseña"
        self.fields["password2"].label = "Confirmar contraseña"
        self.fields["password2"].help_text = ""

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    @transaction.atomic
    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.rol = RolUsuario.CLIENTE
        usuario.save()
        Cliente.objects.create(usuario=usuario)  # el sexo se completa después
        return usuario
