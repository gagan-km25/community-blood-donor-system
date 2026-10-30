"""Forms for creating/updating blood requests and related actions."""

import django.forms as forms

from donors.models import BloodGroup

from .models import BloodRequest, RequestStatus, Urgency


class BloodRequestForm(forms.ModelForm):
    """Create/update a blood request. All validation is server-side."""

    class Meta:
        model = BloodRequest
        fields = [
            'patient_name', 'blood_group', 'units_needed', 'urgency',
            'hospital_name', 'hospital_city', 'needed_by', 'contact_number',
            'notes',
        ]
        widgets = {
            'patient_name': forms.TextInput(
                attrs={'placeholder': 'Optional — beneficiary name'}
            ),
            'hospital_name': forms.TextInput(
                attrs={'placeholder': 'e.g. City General Hospital'}
            ),
            'hospital_city': forms.TextInput(attrs={'placeholder': 'e.g. Pune'}),
            'needed_by': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'contact_number': forms.TextInput(
                attrs={'placeholder': 'Phone number for this request'}
            ),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['blood_group'].choices = list(BloodGroup.choices)
        self.fields['urgency'].choices = list(Urgency.choices)
        self.fields['needed_by'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M']

    def clean_needed_by(self):
        from django.utils import timezone
        needed_by = self.cleaned_data.get('needed_by')
        if needed_by and needed_by <= timezone.now():
            raise forms.ValidationError(
                'The required date/time must be in the future.'
            )
        return needed_by


class StatusUpdateForm(forms.Form):
    """Owner/admin status action form.

    ``to_status`` MUST keep its choices: a ChoiceField with an empty choices
    list silently rejects every submitted value, which made this form invalid
    for all UI buttons and surfaced as 'Invalid status action.' on the detail
    page (regression-tested in blood_requests.tests). Which transitions are
    *legal* for a given current status is enforced separately by
    services.transition — defence in depth, not this field's job.
    """

    to_status = forms.ChoiceField(choices=RequestStatus.choices,
                                  widget=forms.HiddenInput)
    units_fulfilled = forms.IntegerField(
        required=False, min_value=0, max_value=10,
        widget=forms.NumberInput(attrs={'min': 0}),
    )
    note = forms.CharField(
        max_length=200, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Optional note'}),
    )


class AbuseReportForm(forms.Form):
    reason = forms.CharField(
        max_length=1000, required=True,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': 'Why are you reporting this request?',
        }),
    )
