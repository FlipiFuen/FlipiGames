from django import forms 
from .models import Torneo

class TorneoRegistroForm(forms.ModelForm):
    
    confirmacion = forms.BooleanField(
        required = True,
        label = "Confirmo que quiero participar en el torneo de esta semana"
    )
    
    class Meta:
        model = Torneo
        fields = ["confirmacion"]
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
        return instance 