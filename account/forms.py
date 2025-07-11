from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Account
from main.models import Client


class RegistrationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Account
        fields = ('first_name', 'last_name', 'email')


class CustomerRegistrationForm(RegistrationForm):
    """Form for clients to register themselves, or for meter readers to register them."""
    pass


class MeterReaderRegistrationForm(RegistrationForm):
    """Form for admins to register a new meter reader."""
    pass


class AdminUserCreationForm(forms.Form):
    """
    A unified form for administrators to create new users (both Customers and
    Meter Readers). It dynamically requires client-specific fields based on the
    selected role.
    """
    ROLE_CHOICES = (
        (Account.Role.CUSTOMER, 'Customer'),
        (Account.Role.METER_READER, 'Meter Reader'),
    )

    first_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}))
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True, widget=forms.Select(attrs={'class': 'form-control'}))
    contact_number = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254...'}))
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'e.g., Kahawa Estate'}))

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Account.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        contact_number = cleaned_data.get('contact_number')
        address = cleaned_data.get('address')

        if role == Account.Role.CUSTOMER:
            if not contact_number:
                self.add_error('contact_number', 'This field is required for customers.')
            if not address:
                self.add_error('address', 'This field is required for customers.')
        return cleaned_data


class VerificationForm(forms.Form):
    code = forms.CharField(
        max_length=6, 
        required=True, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter OTP'})
    )
class FormSettings(forms.ModelForm):
   def __init__(self, *args, **kwargs):
      super(FormSettings, self).__init__(*args, **kwargs)
      for field in self.visible_fields():
         field.field.widget.attrs['class'] = 'form-control form-control-user'


class RegistrationForm(FormSettings):
   def save(self, commit=True):
      user = super(RegistrationForm, self).save(commit=False)
      password = self.cleaned_data.get("password")
      if password:
         user.set_password(password)
      if commit:
         user.save()
      return user

   def __init__(self, *args, **kwargs):
      super(RegistrationForm, self).__init__(*args, **kwargs)
      if kwargs.get('instance'):
         instance = kwargs.get('instance').__dict__
         self.fields['password'].required = False
         for field in RegistrationForm.Meta.fields:
            self.fields[field].initial = instance.get(field)
         if self.instance.pk is not None:
            self.fields['password'].widget.attrs['placeholder'] = "Fill this only if you wish to update password"
         else:
            self.fields['first_name'].required = True
            self.fields['last_name'].required = True

   def clean_email(self, *args, **kwargs):
      formEmail = self.cleaned_data['email'].lower()

      # domain = formEmail.split('@')[1]
      # domain_list = ["ssct.edu.ph"]
      # if domain not in domain_list:
      #    raise forms.ValidationError("Please enter ssct gsuite email")
      if self.instance.pk is None: 
         if Account.objects.filter(email=formEmail).exists():
               raise forms.ValidationError(
                  "The given email is already registered")
      else:  # Update
         dbEmail = self.Meta.model.objects.get(
               id=self.instance.pk).email.lower()
         if dbEmail != formEmail:  # There has been changes
               if Account.objects.filter(email=formEmail).exists():
                  raise forms.ValidationError(
                     "The given email is already registered")
      return formEmail

   class Meta:
      model = Account
      fields = ['last_name', 'first_name', 'email', 'password',]
      widgets = {
      'last_name':forms.TextInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'Last name' }),
      'first_name':forms.TextInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'First Name' }),
      'password': forms.PasswordInput(attrs={'type': 'password', 'class': 'form-control', 'placeholder':'Password' }),
      'email': forms.TextInput(attrs={'type': 'email', 'class': 'form-control', 'placeholder':'Email' }),
   }


class UpdateProfileForm(FormSettings):
   phone_number = forms.CharField(max_length=20, required=False)

   def save(self, commit=True):
      user = super(UpdateProfileForm, self).save(commit=False)
      password = self.cleaned_data.get("password")
      if password:
         user.set_password(password)
      if commit:
         user.save()
      return user

   def __init__(self, *args, **kwargs):
      super(UpdateProfileForm, self).__init__(*args, **kwargs)
      if kwargs.get('instance'):
         instance = kwargs.get('instance').__dict__
         self.fields['password'].required = False
         for field in UpdateProfileForm.Meta.fields:
            self.fields[field].initial = instance.get(field)
         if self.instance.pk is not None:
            self.fields['password'].widget.attrs['placeholder'] = "Fill this only if you wish to update password"
         else:
            self.fields['first_name'].required = True
            self.fields['last_name'].required = True

   def clean_email(self, *args, **kwargs):
      formEmail = self.cleaned_data['email'].lower()

      # domain = formEmail.split('@')[1]
      # domain_list = ["ssct.edu.ph"]
      # if domain not in domain_list:
      #    raise forms.ValidationError("Please enter ssct gsuite email")
      if self.instance.pk is None: 
         if Account.objects.filter(email=formEmail).exists():
               raise forms.ValidationError(
                  "The given email is already registered")
      else:  # Update
         dbEmail = self.Meta.model.objects.get(
               id=self.instance.pk).email.lower()
         if dbEmail != formEmail:  # There has been changes
               if Account.objects.filter(email=formEmail).exists():
                  raise forms.ValidationError(
                     "The given email is already registered")
      return formEmail

   class Meta:
      model = Account
      exclude = ['last_name', 'first_name', 'email', 'department']
      fields = ['phone_number', 'password',]
      widgets = {
      'password': forms.PasswordInput(attrs={'type': 'password', 'class': 'form-control', 'placeholder':'Password' }),
   }



class UpdateUserForm(FormSettings):
   def save(self, commit=True):
      user = super(UpdateUserForm, self).save(commit=False)
      password = self.cleaned_data.get("password")
      if password:
         user.set_password(password)
      if commit:
         user.save()
      return user

   def __init__(self, *args, **kwargs):
      super(UpdateUserForm, self).__init__(*args, **kwargs)
      if kwargs.get('instance'):
         instance = kwargs.get('instance').__dict__
         self.fields['password'].required = False
         for field in UpdateUserForm.Meta.fields:
            self.fields[field].initial = instance.get(field)
         if self.instance.pk is not None:
            self.fields['password'].widget.attrs['placeholder'] = "Fill this only if you wish to update password"
         else:
            self.fields['first_name'].required = True
            self.fields['last_name'].required = True

   def clean_email(self, *args, **kwargs):
      formEmail = self.cleaned_data['email'].lower()

      domain = formEmail.split('@')[1]
      domain_list = ["ssct.edu.ph"]
      if domain not in domain_list:
         raise forms.ValidationError("Please enter ssct gsuite email")
      if self.instance.pk is None: 
         if Account.objects.filter(email=formEmail).exists():
               raise forms.ValidationError(
                  "The given email is already registered")
      else:  # Update
         dbEmail = self.Meta.model.objects.get(
               id=self.instance.pk).email.lower()
         if dbEmail != formEmail:  # There has been changes
               if Account.objects.filter(email=formEmail).exists():
                  raise forms.ValidationError(
                     "The given email is already registered")
      return formEmail

   class Meta:
      model = Account
      exclude = ['verified',]
      fields = ['last_name', 'first_name', 'email', 'password']
      widgets = {
      'last_name':forms.TextInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'Last name' }),
      'first_name':forms.TextInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder':'First Name' }),
      'email': forms.TextInput(attrs={'type': 'email', 'class': 'form-control', 'placeholder':'Email' }),
      'password': forms.PasswordInput(attrs={'type': 'password', 'class': 'form-control', 'placeholder':'Password' }),
   }





class VerificationForm(forms.ModelForm):
   class Meta:
      model = Account
      fields = ['otp']
      exclude = ['last_name', 'first_name', 'email', 'department', 'password',]
      widgets = {
         'otp':forms.TextInput(attrs={'type': 'number', 'class': 'form-control', 'placeholder':'OTP' }),
      }


class CustomerRegistrationForm(RegistrationForm):
    contact_number = forms.CharField(max_length=13, widget=forms.TextInput(attrs={'placeholder': 'Contact Number'}))
    address = forms.CharField(max_length=250, widget=forms.TextInput(attrs={'placeholder': 'Address'}))

    def __init__(self, *args, **kwargs):
        super(CustomerRegistrationForm, self).__init__(*args, **kwargs)
        self.fields['address'].widget.attrs.update({'placeholder': 'e.g., Kahawa Wendani Estate'})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = Account.Role.CUSTOMER
        if commit:
            user.save()
            Client.objects.create(
                name=user,
                contact_number=self.cleaned_data.get('contact_number'),
                address=self.cleaned_data.get('address'),
                status='Pending'
            )
        return user

    class Meta(RegistrationForm.Meta):
        fields = RegistrationForm.Meta.fields + ['contact_number', 'address']


class MeterReaderRegistrationForm(RegistrationForm):

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = Account.Role.METER_READER
        if commit:
            user.save()
        return user

class AdminRegistrationForm(RegistrationForm):

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = Account.Role.ADMIN
        user.is_superuser = True
        user.is_staff = True
        if commit:
            user.save()
        return user