from django.shortcuts import render, HttpResponseRedirect, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from .decorators import admin_required, meter_reader_required
from .forms import CustomerRegistrationForm, MeterReaderRegistrationForm, RegistrationForm, VerificationForm, AdminRegistrationForm, AdminUserCreationForm, MeterReaderCreationForm
from main.models import *
from django.conf import settings
import sweetify
import random as r
import smtplib


def landingpage(request):
    return render(request, 'account/landingpage.html')


def generate_otp():
    otp = ""
    for i in range(r.randint(5, 8)):
        otp += str(r.randint(1, 9))
    return otp


def login_view(request):
    role = request.GET.get('role')

    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        user = authenticate(request, email=email, password=password)
        if user is not None:
            if not user.verified:
                # If user is not verified, send OTP for email verification.
                otp = generate_otp()
                user.otp = otp
                user.save()

                # Send OTP to user's email
                subject = 'Verify Your Email Address'
                message = f'Welcome! Your verification code is: {otp}'
                from_email = settings.EMAIL_HOST_USER
                recipient_list = [user.email]
                send_mail(subject, message, from_email, recipient_list)

                login(request, user)
                return HttpResponseRedirect(reverse('verify'))
            
            # If user is already verified, log them in directly.
            login(request, user)
            sweetify.success(request, 'Login Successfully')
            if user.role == Account.Role.ADMIN:
                if not Metric.objects.exists():
                    Metric.objects.create(consump_amount=1, penalty_amount=1)
                return HttpResponseRedirect(reverse('dashboard'))
            elif user.role == Account.Role.METER_READER:
                return HttpResponseRedirect(reverse('meter_reader_dashboard'))
            elif user.role == Account.Role.CUSTOMER:
                return HttpResponseRedirect(reverse('client_dashboard'))
            else:
                return HttpResponseRedirect(reverse('landingpage'))
        else:
            sweetify.error(request, 'Invalid Credentials')
            return render(request, 'account/login.html', {'error': 'Invalid Credentials', 'role': role})

    # Clear any existing messages
    storage = messages.get_messages(request)
    storage.used = True

    return render(request, 'account/login.html', {'role': role})


def verify(request):
    otp_form = VerificationForm()
    context = {
        'otp_form': otp_form
    }
    if request.method == 'POST':
        user = request.user
        otp_form = VerificationForm(request.POST)
        user_otp = request.POST['otp']
        otp = int(user_otp)
        if otp == user.otp:
            user = request.user
            user.verified = True
            user.save()
            sweetify.success(request, 'Verification successful. Welcome!')
            # Redirect to the appropriate dashboard based on user role
            if user.role == Account.Role.ADMIN:
                return HttpResponseRedirect(reverse('dashboard'))
            elif user.role == Account.Role.METER_READER:
                return HttpResponseRedirect(reverse('meter_reader_dashboard'))
            elif user.role == Account.Role.CUSTOMER:
                return HttpResponseRedirect(reverse('ongoing_bills'))
            else:
                return HttpResponseRedirect(reverse('landingpage'))
        else:
            print("failed")
            return render(request, 'account/verify.html', {'error': 'OTP is incorrect!', 'otp_form': otp_form})

    return render(request, 'account/verify.html', context)





def logout_view(request):
    user_role = request.user.role
    logout(request)
    if user_role == Account.Role.ADMIN or user_role == Account.Role.METER_READER:
        return redirect('login')
    else:
        return redirect('landingpage')


def customer_register_view(request):
    form = CustomerRegistrationForm()
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            sweetify.success(request, 'Customer account created successfully.')
            return HttpResponseRedirect(reverse('login'))
        else:
            sweetify.error(request, 'Please correct the errors below.')
    context = {
        'form': form,
        'title': 'Customer Registration'
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
def meter_reader_register_view(request):
    logger.info('Meter reader registration view started.')
    form = RegistrationForm()
    if request.method == 'POST':
        logger.info('POST request received.')
        form = RegistrationForm(request.POST)
        if form.is_valid():
            logger.info('Form is valid.')
            user = form.save(commit=False)
            user.role = Account.Role.METER_READER
            user.save()
            sweetify.success(request, 'Meter Reader account created successfully.')
            logger.info('Meter reader created successfully.')
            return HttpResponseRedirect(reverse('users'))
        else:
            logger.error(f'Form is invalid: {form.errors}')
            sweetify.error(request, 'Please correct the errors below.')
    context = {
        'form': form,
        'title': 'Meter Reader Registration'
    }
    logger.info('Rendering registration page.')
    return render(request, 'account/meter_reader_register.html', context)


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
                password=form.cleaned_data['password'],
                role=role
            )
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


@login_required(login_url='login')
@meter_reader_required
def meter_reader_register_user_view(request):
    form = CustomerRegistrationForm()
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = Account.Role.CUSTOMER
            user.save()
            sweetify.success(request, 'Client account created successfully!')
            return redirect('clients')
    context = {
        'form': form,
        'title': 'Register Client'
    }
    return render(request, 'account/register.html', context)





@login_required(login_url='login')
@admin_required
def add_meter_reader(request):
    if request.method == 'POST':
        form = MeterReaderCreationForm(request.POST)
        if form.is_valid():
            Account.objects.create_user(
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                role=Account.Role.METER_READER,
                verified=True
            )
            sweetify.success(request, 'Meter Reader account created successfully.')
            return redirect('users')
        else:
            sweetify.error(request, 'Please correct the errors below.')
    else:
        form = MeterReaderCreationForm()

    context = {
        'form': form,
        'title': 'Add Meter Reader'
    }
    return render(request, 'account/add_meter_reader.html', context)
