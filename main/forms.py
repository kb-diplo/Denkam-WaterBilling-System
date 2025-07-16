from django import forms
from .models import *


class BillForm(forms.ModelForm):
    class Meta:
        model = WaterBill
        fields = ['name','meter_consumption', 'status', 'duedate', 'penaltydate']
        exclude = ['penalty', 'bill',]
        widgets = {
            'name': forms.Select(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'Name' }),
            'meter_consumption': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder':'0.00' }),
            'status': forms.Select(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'Pay Status' }),
            'duedate': forms.TextInput(attrs={'type': 'date', 'class': 'form-control', 'placeholder':'Due Date' }),
            'penaltydate': forms.TextInput(attrs={'type': 'date', 'class': 'form-control', 'placeholder':'Penalty Date' }),
        }


class ClientUpdateForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'meter_number', 'address', 'contact_number', 'status']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'meter_number': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Meter Number'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Kahawa Estate'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254...'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

class ClientForm(forms.ModelForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'}))

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Account.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already in use. Please use a different one.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")

    class Meta:
        model = Client
        fields = ['meter_number', 'first_name', 'middle_name', 'last_name', 'email', 'password', 'contact_number', 'address', 'status']
        widgets = {
            'meter_number': forms.TextInput(attrs={'type': 'number', 'class': 'form-control', 'placeholder': '0000000'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Middle Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254...'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Kahawa Estate'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }


class MetricsForm(forms.ModelForm):
    class Meta:
        model = Metric
        fields = '__all__'
        widgets = {
            'consump_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder':'0.00' }),
            'penalty_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder':'0.00' })
        }

class MeterReadingForm(forms.Form):
    reading = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 
            'step': '0.01', 
            'placeholder': 'Enter meter reading (e.g., 123.45)'
        })
    )