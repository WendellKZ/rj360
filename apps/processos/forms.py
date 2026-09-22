from django import forms

from .models import Andamento, Documento, Credor, Parcela, Prazo, ProcessoRJ


class ProcessoForm(forms.ModelForm):
    class Meta:
        model = ProcessoRJ
        fields = [
            "empresa", "numero_cnj", "fase", "valor_divida",
            "tribunal", "datajud_alias", "comarca", "vara", "juiz", "advogado",
            "administrador_judicial", "aj_email", "aj_telefone",
            "data_distribuicao", "data_deferimento", "data_edital_52", "data_plano",
            "data_edital_53", "data_agc", "data_concessao", "encerrado_em",
            "stay_prorrogado", "observacoes",
        ]
        widgets = {
            campo: forms.DateInput(attrs={"type": "date"})
            for campo in [
                "data_distribuicao", "data_deferimento", "data_edital_52", "data_plano",
                "data_edital_53", "data_agc", "data_concessao", "encerrado_em",
            ]
        } | {"observacoes": forms.Textarea(attrs={"rows": 3})}


class AndamentoForm(forms.ModelForm):
    class Meta:
        model = Andamento
        fields = ["data", "tipo", "titulo", "descricao", "visivel_cliente"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "descricao": forms.Textarea(attrs={"rows": 3}),
        }


class PrazoForm(forms.ModelForm):
    class Meta:
        model = Prazo
        fields = ["titulo", "base_legal", "tipo", "data_inicio", "data_fim", "responsavel", "observacoes"]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_fim": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }


class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ["titulo", "categoria", "arquivo", "data_referencia", "visivel_cliente"]
        widgets = {"data_referencia": forms.DateInput(attrs={"type": "date"})}


class CredorForm(forms.ModelForm):
    class Meta:
        model = Credor
        fields = ["nome", "documento", "classe", "valor_arrolado", "valor_habilitado", "situacao", "sujeito_rj"]


class ParcelaForm(forms.ModelForm):
    class Meta:
        model = Parcela
        fields = ["descricao", "classe", "vencimento", "valor_previsto", "valor_pago", "pago_em", "status"]
        widgets = {
            "vencimento": forms.DateInput(attrs={"type": "date"}),
            "pago_em": forms.DateInput(attrs={"type": "date"}),
        }
