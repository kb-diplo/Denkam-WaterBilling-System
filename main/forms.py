from django import forms
from .models import *


class BillForm(forms.ModelForm):
    class Meta:
        model = WaterBill
        fields = ['name','meter_consumption', 'status', 'duedate', 'penaltydate']
        exclude = ['penalty', 'bill',]
        widgets = {
            'name': forms.Select(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'Name' }),
            'meter_consumption': forms.TextInput(attrs={'type': 'number', 'class': 'form-control', 'placeholder':'00000000' }),
            'status': forms.Select(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'Pay Status' }),
            'duedate': forms.TextInput(attrs={'type': 'date', 'class': 'form-control', 'placeholder':'Due Date' }),
            'penaltydate': forms.TextInput(attrs={'type': 'date', 'class': 'form-control', 'placeholder':'Penalty Date' }),
        }


class ClientUpdateForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'middle_name', 'contact_number', 'address']
        widgets = {
            'first_name': forms.TextInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'First Name' }),
            'last_name': forms.TextInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'Last Name' }),
            'middle_name': forms.TextInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'Middle Name' }),
            'contact_number': forms.TextInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'+254...' }),
            'address': forms.TextInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'e.g., Kahawa Estate' }),
        }

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = '__all__'
        widgets = {
            'meter_number': forms.TextInput(attrs={'type': 'number', 'class': 'form-control', 'placeholder':'0000000' }),
            'first_name': forms.TextInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'First Name' }),
            'middle_name': forms.TextInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'Middle Name' }),
            'last_name': forms.TextInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'Last Name' }),
            'contact_number': forms.TextInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'+254...' }),
            'address': forms.TextInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'e.g., Kahawa Estate' }),
            'status': forms.Select(attrs={'class': 'form-control', 'placeholder':'Select' }),
        }


class MetricsForm(forms.ModelForm):
    class Meta:
        model = Metric
        fields = '__all__'
        widgets = {
            'consump_amount': forms.TextInput(attrs={'type': 'number', 'class': 'form-control', 'placeholder':'00000000' }),
            'penalty_amount': forms.TextInput(attrs={'type': 'number', 'class': 'form-control', 'placeholder':'00000000' })
        }

class MeterReadingForm(forms.ModelForm):
    class Meta:
        model = WaterBill
        fields = ['reading']
        widgets = {
            'reading': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter meter reading'}),
        }