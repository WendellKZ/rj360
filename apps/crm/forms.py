from django import forms

from .models import Atividade, Lead


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            "razao_social", "nome_fantasia", "cnpj", "porte", "setor", "cidade", "uf",
            "contato_nome", "contato_cargo", "contato_email", "contato_telefone",
            "origem", "situacao_juridica", "estagio", "valor_estimado",
            "responsavel", "proximo_contato", "motivo_perda", "observacoes",
        ]
        widgets = {
            "proximo_contato": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }


class AtividadeForm(forms.ModelForm):
    class Meta:
        model = Atividade
        fields = ["data", "tipo", "titulo", "descricao"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "descricao": forms.Textarea(attrs={"rows": 3}),
        }
