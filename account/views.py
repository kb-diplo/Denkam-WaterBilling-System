from django.shortcuts import render, HttpResponseRedirect, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from .decorators import admin_required, meter_reader_required
from .forms import CustomerRegistrationForm, MeterReaderRegistrationForm, RegistrationForm, VerificationForm, AdminRegistrationForm, AdminUserCreationForm
from main.models import *
from django.conf import settings
import sweetify
import random as r
import smtplib


def landingpage(request):
    return render(request, 'account/landingpage.html')


def login_view(request):
    role = request.GET.get('role')

    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        user = authenticate(request, email=email, password=password)
        if user is not None:
            # Set user as verified and log them in directly
            if not user.verified:
                user.verified = True
                user.save()
            login(request, user)
            sweetify.success(request, 'Login Successful')
            if user.role == Account.Role.ADMIN:
                if not Metric.objects.exists():
                    Metric.objects.create(consump_amount=1, penalty_amount=1)
                return HttpResponseRedirect(reverse('main:dashboard'))
            elif user.role == Account.Role.METER_READER:
                return HttpResponseRedirect(reverse('account:meter_reading_dashboard'))
            elif user.role == Account.Role.CUSTOMER:
                return HttpResponseRedirect(reverse('main:client_dashboard'))
            else:
                return HttpResponseRedirect(reverse('landingpage'))
        else:
            sweetify.error(request, 'Invalid Credentials')
            return render(request, 'account/login.html', {'error': 'Invalid Credentials', 'role': role})

    return render(request, 'account/login.html', {'role': role})


from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest
from django.contrib import messages
from django.conf import settings

@csrf_protect


def logout_view(request):
    user_role = None
    if request.user.is_authenticated:
        user_role = getattr(request.user, 'role', None)
    
    # Log the user out
    logout(request)
    
    # Redirect to respective login page based on role
    if user_role == Account.Role.ADMIN:
        return redirect('{}?role=admin'.format(reverse('account:login')))
    elif user_role == Account.Role.METER_READER:
        return redirect('{}?role=meter_reader'.format(reverse('account:login')))
    else:
        # Default redirect to landing page for customers
        return redirect('landingpage')


def customer_register_view(request):
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.role = Account.Role.CUSTOMER
                user.is_active = True
                user.save()
                messages.success(request, 'Account created successfully! You can now log in.')
                return redirect('login')
            except Exception as e:
                print(f"Error creating user: {str(e)}")
                messages.error(request, f'Error creating account: {str(e)}')
        else:
            # Log form errors for debugging
            print("Form errors:", form.errors)
    else:
        form = CustomerRegistrationForm()
    
    context = {
        'form': form,
        'title': 'Create an Account',
    }
    return render(request, 'account/register.html', context)


@login_required(login_url='login')
@user_passes_test(lambda u: u.is_superuser)
def admin_register_view(request):
    form = AdminRegistrationForm()
    if request.method == 'POST':
        form = AdminRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            sweetify.success(request, 'Administrator account created successfully.')
            return HttpResponseRedirect(reverse('users'))
        else:
            sweetify.error(request, 'Please correct the errors below.')
    context = {
        'form': form,
        'title': 'Administrator Registration'
    }
    return render(request, 'account/register.html', context)


import logging
from django.http import HttpResponse

logger = logging.getLogger(__name__)

@login_required(login_url='login')
@admin_required
def admin_register_user_view(request):
    """
    Allows an admin to register a new user (Customer or Meter Reader) using a unified form.
    """
    if request.method == 'POST':
        form = AdminUserCreationForm(request.POST)
        if form.is_valid():
            role = form.cleaned_data['role']
            
            # Create the user account
            user = Account.objects.create_user(
                email=form.cleaned_data['email'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                password=form.cleaned_data['password1']
            )
            user.role = role
            user.save()

            # If the user is a customer, create their client profile
            if role == Account.Role.CUSTOMER:
                Client.objects.create(
                    name=user,
                    contact_number=form.cleaned_data['contact_number'],
                    address=form.cleaned_data['address']
                )

            sweetify.success(request, f'{user.get_role_display()} account created successfully!')
            return HttpResponseRedirect(reverse('users'))
        else:
            sweetify.error(request, 'Please correct the errors below.')
    else:
        form = AdminUserCreationForm()

    context = {
        'title': 'Register New User',
        'form': form,
    }
    return render(request, 'account/admin_register_user.html', context)


def meter_reading_dashboard(request):
    context = {
        'title': 'Meter Reading Dashboard'
    }
    return render(request, 'account/meter_reader_dashboard.html', context)


from django.contrib.auth import logout as django_logout
from django.urls import reverse


def logout_view(request):
    user_role = None
    if request.user.is_authenticated:
        user_role = getattr(request.user, 'role', None)
    
    # Log the user out
    django_logout(request)
    
    # Redirect to respective login page based on role
    if user_role == 'ADMIN':
        return redirect('{}?role=admin'.format(reverse('account:login')))
    elif user_role == 'METER_READER':
        return redirect('{}?role=meter_reader'.format(reverse('account:login')))
    elif user_role == 'CUSTOMER':
        return redirect('{}?role=customer'.format(reverse('account:login')))
    else:
        # Default redirect to general login page
        return redirect('account:login')
