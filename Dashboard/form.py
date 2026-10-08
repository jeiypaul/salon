# forms.py
from datetime import date

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Booking


from django import forms
from .models import GalleryItem


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ["name", "email", "service", "date", "time", "notes"]

    def clean_date(self):
        d = self.cleaned_data["date"]
        if d < date.today():
            raise forms.ValidationError("Please choose today or a future date.")
        return d

    def clean(self):
        data = super().clean()
        d, t = data.get("date"), data.get("time")
        if d and t and Booking.objects.filter(date=d, time=t).exclude(status="cancelled").exists():
            raise forms.ValidationError("That time slot is already booked. Please pick another time.")
        return data


class StaffAuthForm(AuthenticationForm):
    """Login form that only lets staff users into the dashboard."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)  # keeps the inactive-account check
        if not user.is_staff:
            raise forms.ValidationError(
                "This account doesn't have admin access.",
                code="no_access",
            )

class GalleryItemForm(forms.ModelForm):
    class Meta:
        model = GalleryItem
        fields = ["name", "description", "image"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Knotless Braids"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Short description of the style"}),
        }