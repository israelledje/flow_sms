from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm, PasswordResetForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import SenderID  # Import the SenderID model

User = get_user_model()

class UserRegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'nom', 'prenom', 
                 'telephone', 'nationalite', 'ville', 'pays', 'account_type', 
                 'secteur_activite']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Champs supplémentaires pour les entreprises
        self.fields['niu'] = forms.CharField(required=False, label="NIU")
        self.fields['rccm'] = forms.CharField(required=False, label="RCCM")
        self.fields['site_web'] = forms.URLField(required=False, label="Site web")
        self.fields['description'] = forms.CharField(widget=forms.Textarea, required=False)
        self.fields['nombre_employes'] = forms.IntegerField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        account_type = cleaned_data.get('account_type')
        
        if account_type == User.AccountTypes.ENTREPRISE:
            if not cleaned_data.get('niu'):
                raise ValidationError("Le NIU est obligatoire pour les entreprises")
            if not cleaned_data.get('rccm'):
                raise ValidationError("Le RCCM est obligatoire pour les entreprises")
        return cleaned_data

class AccountDeactivationForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput, 
                             label="Mot de passe",
                             help_text="Entrez votre mot de passe pour confirmer la désactivation")
    reason = forms.CharField(widget=forms.Textarea, 
                           label="Raison de la fermeture",
                           help_text="Merci de nous indiquer la raison de votre départ")

class SenderIDForm(forms.ModelForm):
    class Meta:
        model = SenderID
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'block w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-royal-blue focus:border-royal-blue text-sm',
                'placeholder': 'Ex: FLOWSMS'
            }),
            'description': forms.Textarea(attrs={
                'class': 'block w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-royal-blue focus:border-royal-blue text-sm',
                'placeholder': 'Description de l\'utilisation prévue de ce Sender ID',
                'rows': 3
            })
        }

    def clean_name(self):
        name = self.cleaned_data['name'].upper()
        if len(name) > 11:
            raise ValidationError("Le Sender ID ne doit pas dépasser 11 caractères")
        if not name.isalnum():
            raise ValidationError("Le Sender ID ne doit contenir que des lettres et des chiffres")
        return name

class SenderIDAdminForm(forms.ModelForm):
    class Meta:
        model = SenderID
        fields = ['status', 'rejection_reason']
        widgets = {
            'rejection_reason': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Raison du rejet (obligatoire si le statut est "Rejeté")'
            })
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        rejection_reason = cleaned_data.get('rejection_reason')

        if status == SenderID.Status.REJETE and not rejection_reason:
            raise ValidationError("Une raison de rejet est requise lorsque le statut est 'Rejeté'")

        return cleaned_data
