from django import forms
from .models import User

class RegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']


class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)


class PasswordResetForm(forms.Form):
    email = forms.EmailField()
class VerifyEmailForm(forms.Form):
    code = forms.CharField(max_length=6, label="Введите код с email")

class DeleteAccountForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        label="Код из письма",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Введите код"})
    )
class ForgotUsernameForm(forms.Form):
    email = forms.EmailField()