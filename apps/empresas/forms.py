from django import forms

from .models import Contato, Empresa


class EmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = [
            "razao_social", "nome_fantasia", "cnpj", "porte", "atividade", "situacao",
            "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf",
            "telefone", "email", "site", "responsavel", "inicio_contrato", "observacoes",
        ]
        widgets = {
            "inicio_contrato": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }


class ContatoForm(forms.ModelForm):
    class Meta:
        model = Contato
        fields = ["nome", "cargo", "email", "telefone", "principal"]
