"""Registration and login forms."""

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

from blood_requests.models import phone_validator


class RegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Password', strip=False, widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label='Confirm password', strip=False, widget=forms.PasswordInput,
    )
    phone = forms.CharField(
        label='Phone number (optional, for your profiles)',
        required=False, validators=[phone_validator],
        widget=forms.TextInput(attrs={'placeholder': 'e.g. +91 98765 43210'}),
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name']
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Pick a username'}),
            'email': forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
            'first_name': forms.TextInput(attrs={'placeholder': 'Your name'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                'An account with this email already exists.'
            )
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('The two password fields did not match.')
        if password1:
            validate_password(password2)
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        # set_password hashes the password; it is never stored in plaintext.
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(strip=False, widget=forms.PasswordInput)
