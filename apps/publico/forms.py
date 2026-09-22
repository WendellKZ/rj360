from django import forms

from .models import Diagnostico


class ContatoDiagnosticoForm(forms.ModelForm):
    """Dados de contato pedidos depois do resultado do diagnostico."""

    class Meta:
        model = Diagnostico
        fields = ["nome", "empresa", "telefone", "email"]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Seu nome"}),
            "empresa": forms.TextInput(attrs={"placeholder": "Nome da empresa"}),
            "telefone": forms.TextInput(attrs={"placeholder": "(00) 00000-0000"}),
            "email": forms.EmailInput(attrs={"placeholder": "voce@empresa.com.br"}),
        }

    def clean(self):
        dados = super().clean()
        if not dados.get("telefone") and not dados.get("email"):
            raise forms.ValidationError("Informe ao menos um telefone ou um e-mail para retornarmos.")
        return dados
