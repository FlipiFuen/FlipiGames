from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django import forms

class FormularioRegistroUsuario(UserCreationForm):
    email = forms.EmailField(required=True)
    
    def __init__(self, *args, **kwargs):
        # Acepta tanto 'password' como 'password1' en los datos POST.
        # Algunos tests o clientes envían 'password' en lugar de 'password1',
        # así que mapeamos ese valor si es necesario.
        data = kwargs.get("data")

        if data is None and args:
            data = args[0]

        if data is not None:
            data = data.copy()

            if "password" in data and "password1" not in data:
                data["password1"] = data.get("password")

            if "password" in data and "password2" not in data:
                data["password2"] = data.get("password")

            if "data" in kwargs:
                kwargs["data"] = data
            elif args:
                args = (data,) + args[1:]
        super().__init__(*args, **kwargs)
        
    class Meta:
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)
        
    def save(self, commit=True):
        user = super().save(commit=False) # Creamos el usuario sin guardar de momento
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            
        return user
    
    def clean_email(self):
        """
        Valida que el email no esté ya registrado en el sistema
        """
        email = self.cleaned_data.get("email")
        
        # Usamos "email__iexact" para realizar una búsqueda insensible a mayúsculas y minúsculas
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Este correo electrónico ya está registrado por otro usuario")
        
        return email

class FormularioCambiarEmail(forms.ModelForm):
    
    email = forms.EmailField(label = "Nuevo Correo Electrónico", required = True)
    
    def clean_email(self):
        """
        Valida que el nuevo email no esté ya registrado en el sistema
        """
        email = self.cleaned_data.get("email")
            
        # Filtramos los usuarios con ese email
        query = User.objects.filter(email__iexact=email)
            
        # Excluimos el propio registro del usuario de la comprobación
        if self.instance and self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
                
        if query.exists():
            raise forms.ValidationError("Este correo electrónico ya está registrado por otro usuario")
            
        return email

    class Meta:
        model = User
        fields = ('email',)
