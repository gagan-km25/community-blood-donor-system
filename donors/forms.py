"""Forms for donor profile management and public donor search."""

import datetime

import django.forms as forms

from .models import BloodGroup, DonorProfile


class DonorProfileForm(forms.ModelForm):
    """Create/edit a donor profile. Validation lives here (server-side)."""

    class Meta:
        model = DonorProfile
        fields = [
            'full_name', 'blood_group', 'city', 'phone',
            'is_available', 'last_donation_date', 'contact_consent',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'e.g. Priya Sharma'}),
            'city': forms.TextInput(attrs={'placeholder': 'e.g. Pune'}),
            'phone': forms.TextInput(attrs={'placeholder': 'e.g. +91 98765 43210'}),
            'last_donation_date': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'
            ),
        }

    def clean_full_name(self):
        return self.cleaned_data['full_name'].strip()

    def clean_city(self):
        return self.cleaned_data['city'].strip()

    def clean_last_donation_date(self):
        date = self.cleaned_data.get('last_donation_date')
        if date and date > datetime.date.today():
            raise forms.ValidationError(
                'Last donation date cannot be in the future.'
            )
        return date


class DonorSearchForm(forms.Form):
    """GET form used by the public donor search page."""

    AVAILABILITY_CHOICES = [
        ('', 'Any availability'),
        ('available', 'Available now only'),
    ]

    blood_group = forms.ChoiceField(
        choices=[('', 'All blood groups')] + list(BloodGroup.choices),
        required=False,
    )
    city = forms.CharField(
        max_length=80, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Filter by city'})
    )
    availability = forms.ChoiceField(
        choices=AVAILABILITY_CHOICES, required=False,
        widget=forms.Select
    )
