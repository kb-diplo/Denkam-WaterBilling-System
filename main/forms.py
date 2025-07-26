from django import forms
from .models import Client, WaterBill, BillingRate, MeterReading, Metric
from account.models import Account


class BillForm(forms.ModelForm):
    class Meta:
        model = WaterBill
        fields = ['client', 'meter_reading', 'consumption', 'rate', 'penalty_amount', 'status', 'due_date', 'payment_date', 'notes']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-control'}),
            'meter_reading': forms.Select(attrs={'class': 'form-control'}),
            'consumption': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'penalty_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'payment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ClientUpdateForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'})
    )

    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'email', 'middle_name', 'meter_number', 'contact_number', 'address', 'status']
        widgets = {
            'middle_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Middle Name (optional)', 'required': False}),
            'meter_number': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Meter Number'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254...'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Full address'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.account:
            self.fields['first_name'].initial = self.instance.account.first_name
            self.fields['last_name'].initial = self.instance.account.last_name
            self.fields['email'].initial = self.instance.account.email
    
    def clean_contact_number(self):
        contact_number = self.cleaned_data.get('contact_number')
        if not contact_number.startswith('+254'):
            raise forms.ValidationError("Phone number must start with +254")
        if len(contact_number) != 13:
            raise forms.ValidationError("Phone number must be 13 digits including country code")
        return contact_number
    
    def save(self, commit=True):
        client = super().save(commit=False)
        if commit:
            if hasattr(client, 'account'):
                account = client.account
                account.first_name = self.cleaned_data['first_name']
                account.last_name = self.cleaned_data['last_name']
                account.email = self.cleaned_data['email']
                account.save()
            client.save()
        return client

class ClientForm(forms.ModelForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}),
        min_length=8
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'}),
        min_length=8
    )
    first_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )

    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'middle_name', 'email', 'meter_number', 'contact_number', 'address', 'status']
        widgets = {
            'middle_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Middle Name (optional)', 'required': False}),
            'meter_number': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Meter Number'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254...'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Full address'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_contact_number(self):
        contact_number = self.cleaned_data.get('contact_number')
        if not contact_number.startswith('+254'):
            raise forms.ValidationError("Phone number must start with +254")
        if len(contact_number) != 13:
            raise forms.ValidationError("Phone number must be 13 digits including country code")
        return contact_number

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Account.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match')

        return cleaned_data
        
    def save(self, commit=True):
        # Create the Account first with CUSTOMER role
        account = Account.objects.create_user(
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            role=Account.Role.CUSTOMER
        )
        
        # Create the Client with the account
        client = super().save(commit=False)
        client.account = account
        if commit:
            client.save()
        return client


class BillingRateForm(forms.ModelForm):
    class Meta:
        model = BillingRate
        fields = ['name', 'rate', 'min_consumption', 'max_consumption', 'effective_date', 'end_date', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Residential, Commercial'}),
            'rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'min_consumption': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'max_consumption': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Leave blank for no maximum'}),
            'effective_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class MeterReadingValueForm(forms.Form):
    reading = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Enter current meter reading (e.g., 123.45)',
            'min': '0'
        }),
        help_text='Enter the current meter reading value'
    )

    def clean_reading(self):
        reading = self.cleaned_data.get('reading')
        if reading is not None and reading < 0:
            raise forms.ValidationError('Reading value cannot be negative.')
        return reading


class MeterReadingForm(forms.ModelForm):
    class Meta:
        model = MeterReading
        fields = ['client', 'reading_value', 'notes']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-control'}),
            'reading_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Enter meter reading (e.g., 123.45)'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional notes about this reading'
            })
        }


class MetricsForm(forms.ModelForm):
    class Meta:
        model = Metric
        fields = ['consump_amount', 'penalty_amount']
        widgets = {
            'consump_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Enter consumption amount per unit'
            }),
            'penalty_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Enter penalty amount for late payments'
            }),
        }
        help_texts = {
            'consump_amount': 'Amount charged per unit of water consumed',
            'penalty_amount': 'Additional amount charged for late payments',
        }