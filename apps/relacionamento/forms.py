from django import forms

from .models import DocumentoSolicitado, Mensagem, Reuniao


class EnvioDocumentoForm(forms.ModelForm):
    """O que o cliente preenche ao mandar o arquivo pedido."""

    class Meta:
        model = DocumentoSolicitado
        fields = ["arquivo"]

    def clean_arquivo(self):
        arquivo = self.cleaned_data["arquivo"]
        if arquivo.size > 20 * 1024 * 1024:
            raise forms.ValidationError("Arquivo muito grande (limite de 20 MB).")
        return arquivo


class SolicitacaoDocumentoForm(forms.ModelForm):
    class Meta:
        model = DocumentoSolicitado
        fields = ["titulo", "motivo", "prazo"]
        widgets = {"prazo": forms.DateInput(attrs={"type": "date"})}


class ConferenciaDocumentoForm(forms.ModelForm):
    class Meta:
        model = DocumentoSolicitado
        fields = ["status", "observacao_equipe"]


class ReuniaoForm(forms.ModelForm):
    class Meta:
        model = Reuniao
        fields = ["titulo", "quando", "duracao_minutos", "local", "participantes",
                  "pauta", "ata", "status", "visivel_cliente"]
        widgets = {
            "quando": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "pauta": forms.Textarea(attrs={"rows": 3}),
            "ata": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["quando"].input_formats = ["%Y-%m-%dT%H:%M", "%d/%m/%Y %H:%M"]


class MensagemForm(forms.ModelForm):
    class Meta:
        model = Mensagem
        fields = ["texto"]
        widgets = {"texto": forms.Textarea(attrs={"rows": 3, "placeholder": "Escreva sua mensagem"})}
        labels = {"texto": ""}
