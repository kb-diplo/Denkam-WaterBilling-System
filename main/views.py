from django.shortcuts import render, redirect, HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import update_session_auth_hash
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import datetime
from .models import *
from account.models import *
from .forms import *
from .mpesa_utils import initiate_stk_push
from django.db.models import F, Sum
import sweetify
import json
from account.forms import *
from account.decorators import admin_required, customer_or_admin_required, customer_required, admin_or_meter_reader_required, meter_reader_required
from .decorators import client_facing_login_required
from django.utils import timezone
from collections import defaultdict


def landingpage(request):
    return render(request, 'account/landingpage.html')  


@login_required(login_url='login')
@admin_required
def dashboard(request):
    paid_bills_count = WaterBill.objects.filter(status='Paid').count()
    pending_bills_count = WaterBill.objects.filter(status='Pending').count()

    billing_data = {
        'paid': paid_bills_count,
        'pending': pending_bills_count,
    }

    context = {
        'title': 'Dashboard',
        'clients': Client.objects.all().count(),
        'bills': WaterBill.objects.all().count(),
        'ongoingbills': WaterBill.objects.filter(status='Pending'),
        'connecteds': Client.objects.filter(status='Connected').count(),
        'disconnecteds': Client.objects.filter(status='Disconnected').count(),
        'paid_bills_count': paid_bills_count,
        'pending_bills_count': pending_bills_count,
        'billing_data': billing_data,
    }
    return render(request, 'main/dashboard.html', context)


@login_required(login_url='login')
@meter_reader_required
def meter_reader_dashboard(request):
    # Get current month and year
    now = timezone.now()
    current_month = now.month
    current_year = now.year

    # Get all clients
    all_clients = Client.objects.all()
    total_clients_count = all_clients.count()

    # Get IDs of clients who have been billed this month
    billed_client_ids = WaterBill.objects.filter(
        created_on__year=current_year,
        created_on__month=current_month
    ).values_list('name_id', flat=True).distinct()

    billed_clients_count = len(billed_client_ids)
    pending_clients_count = total_clients_count - billed_clients_count

    context = {
        'title': 'Meter Reader Dashboard',
        'clients': all_clients,
        'total_clients_count': total_clients_count,
        'billed_clients_count': billed_clients_count,
        'pending_clients_count': pending_clients_count,
        'billed_client_ids': list(billed_client_ids),
    }
    return render(request, 'main/meter_reader_dashboard.html', context)


@login_required(login_url='login')
@customer_required
def client_dashboard(request):
    try:
        client = request.user.client
        unpaid_bills_count = WaterBill.objects.filter(name=client, status='Pending').count()
        paid_bills_count = WaterBill.objects.filter(name=client, status='Paid').count()
    except Client.DoesNotExist:
        unpaid_bills_count = 0
        paid_bills_count = 0
        
    context = {
        'title': 'Client Dashboard',
        'unpaid_bills_count': unpaid_bills_count,
        'paid_bills_count': paid_bills_count,
    }
    return render(request, 'main/client_dashboard.html', context)

@login_required(login_url='login')
@customer_or_admin_required
def ongoing_bills(request):
    context = {
        'title': 'Ongoing Bills',
        'ongoingbills': WaterBill.objects.filter(status='Pending') if request.user.role == Account.Role.ADMIN else WaterBill.objects.filter(name__name_id=request.user.id, status='Pending'),
        'form': BillForm()
    }
    if request.method == 'POST':
        try: 
            billform = BillForm(request.POST)
            if billform.is_valid():
                billform.save()
                sweetify.toast(request, 'Successfully Added.')
                return HttpResponseRedirect(request.path_info)
        except:
            sweetify.toast(request, 'Invalid Details', icon='error')

    return render(request, 'main/billsongoing.html', context)


@login_required(login_url='login')
@customer_or_admin_required
def history_bills(request):
    context = {
        'title': 'Bills History',
        'billshistory': WaterBill.objects.filter(status='Paid') if request.user.role == Account.Role.ADMIN else WaterBill.objects.filter(name__name=request.user, status='Paid'),
        'form': BillForm()
    }
    return render(request, 'main/billshistory.html', context)

@login_required(login_url='login')
@admin_required
def update_bills(request, pk):
    bill = WaterBill.objects.get(id=pk)
    form = BillForm(instance=bill)
    context = {
        'title': 'Update Bill',
        'bill': bill,
        'form': form,
    }
    if request.method == 'POST':
        form = BillForm(request.POST, instance=bill)
        if form.is_valid():
            form.save()
            sweetify.toast(request, f'{bill} updated successfully.')
            return HttpResponseRedirect(reverse('ongoingbills'))
    return render(request, 'main/billupdate.html', context)


@login_required(login_url='login')
@admin_required
def delete_bills(request, pk):
    bill = WaterBill.objects.get(id=pk)
    context = {
        'title': 'Delete Bill',
        'bill': bill,
    }
    if request.method == 'POST':
        bill.delete()
        sweetify.toast(request, f'{bill} deleted successfully.')
        return HttpResponseRedirect(reverse('ongoingbills'))
    return render(request, 'main/billdelete.html', context)



@client_facing_login_required
def profile(request, pk):
    # Ensure users can only view their own profile, unless they are an admin.
    if not request.user.is_superuser and request.user.id != int(pk):
        sweetify.error(request, "You are not authorized to view this profile.")
        return redirect('client_dashboard')

    user_account = Account.objects.get(id=pk)
    try:
        client_instance = Client.objects.get(name=user_account)
    except Client.DoesNotExist:
        client_instance = None

    if request.method == 'POST':
        # Use the appropriate form based on the user's role
        if request.user.is_superuser:
            client_form = ClientForm(request.POST, instance=client_instance) if client_instance else None
        else:
            client_form = ClientUpdateForm(request.POST, instance=client_instance) if client_instance else None
        
        account_form = UpdateProfileForm(request.POST, instance=user_account)

        if account_form.is_valid() and (client_form is None or client_form.is_valid()):
            user = account_form.save(commit=False)
            password = account_form.cleaned_data.get('password')
            if password:
                user.set_password(password)
            user.save()

            if password:
                update_session_auth_hash(request, user)

            if client_form:
                client_form.save()
            
            sweetify.success(request, 'Profile updated successfully!')
            return redirect('profile', pk=user_account.id)
        else:
            sweetify.error(request, 'Please correct the errors below.')
    else:
        if request.user.is_superuser:
            client_form = ClientForm(instance=client_instance) if client_instance else None
        else:
            client_form = ClientUpdateForm(instance=client_instance) if client_instance else None
        
        account_form = UpdateProfileForm(instance=user_account)

    context = {
        'title': 'Profile',
        'account_form': account_form,
        'client_form': client_form,
        'profile': user_account
    }
    return render(request, 'main/profile.html', context)

@login_required(login_url='login')

@login_required(login_url='login')
@admin_required
def users(request):
    # Get all non-admin users
    all_users = Account.objects.filter(is_superuser=False)

    # Separate users by role
    meter_readers = all_users.filter(role=Account.Role.METER_READER)
    clients = all_users.filter(role=Account.Role.CUSTOMER)

    context = {
        'title': 'Users',
        'meter_readers': meter_readers,
        'clients': clients,
    }
    return render(request, 'main/users.html', context)


@login_required(login_url='login')
@admin_required
@require_POST
def add_as_client(request, pk):
    user = Account.objects.get(id=pk)
    if user.role == 'METER_READER':
        sweetify.error(request, 'A Meter Reader cannot be registered as a Client.')
        return redirect('users')
    if not Client.objects.filter(name=user).exists():
        Client.objects.create(name=user, contact_number='N/A', address='N/A')
        sweetify.success(request, f'{user.first_name} {user.last_name} has been added as a client.')
    else:
        sweetify.warning(request, f'{user.first_name} {user.last_name} is already a client.')
    return redirect('users')


@login_required(login_url='login')
@admin_required
def update_user(request, pk):
    user = Account.objects.get(id=pk)
    form = UpdateUserForm(instance=user)
    context = {
        'title': 'Users',
        'user': user,
        'form': form,
    }
    if request.method == 'POST':
        form = UpdateUserForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            sweetify.toast(request, f'{user} updated sucessfuly')
            return HttpResponseRedirect(reverse('users'))
    return render(request, 'main/userupdate.html', context)

@login_required(login_url='login')
@admin_required
def delete_user(request, pk):
    user = Account.objects.get(id=pk)
    context = {
        'title': 'Users',
        'user': user,
    }
    if request.method == 'POST':
        user.delete()
        sweetify.toast(request, 'Deleted successfuly.')
        return HttpResponseRedirect(reverse('users'))
    return render(request, 'main/userdelete.html', context)

@login_required(login_url='login')
@admin_or_meter_reader_required
def clients(request):
    form = ClientForm()
    context = {
        'title': 'Clients',
        'clients': Client.objects.all(),
        'form': form,
    }
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            form.save()
            sweetify.toast(request, 'Successfully Added.')
            return HttpResponseRedirect(request.path_info)
        else:
            sweetify.toast(request, 'Invalid Details', icon='error')

    return render(request, 'main/clients.html', context)

@login_required(login_url='login')
@admin_required
def client_delete(request,pk):
    client = Client.objects.get(pk=pk)
    user = Account.objects.get(pk=client.name.id)
    user.delete()
    client.delete()
    sweetify.toast(request, 'Successfully Deleted.')
    return redirect('clients')

@login_required(login_url='login')
@admin_or_meter_reader_required
def client_update(request,pk):
    client = Client.objects.get(id=pk)
    form = ClientForm(instance=client)
    context = {
        'title': 'Update Client',
        'client': client,
        'form': form
    }
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            sweetify.success(request, 'Client updated successfully!', persistent=True)
            return HttpResponseRedirect(reverse('clients'))
        else:
            error_list = []
            for field, errors in form.errors.items():
                for error in errors:
                    error_list.append(f"{field.replace('_', ' ').title()}: {error}")
            error_message = "Update failed. " + " ".join(error_list)
            sweetify.error(request, error_message, persistent=True)
    return render(request, 'main/clientupdate.html', context)


@login_required(login_url='login')
@admin_required
def client_delete(request,pk):
    client = Client.objects.get(id=pk)
    context = {
        'title': 'Delete Client',
        'client': client,
    }
    if request.method == 'POST':
        client.delete()
        sweetify.toast(request, 'Client deleted successfully')
        return HttpResponseRedirect(reverse('clients'))
    return render(request, 'main/clientdelete.html', context)



def metrics(request):
    if not Metric.objects.all():
        Metric.objects.create()
    context = {
        'title': 'Metrics',
        'amount': Metric.objects.get(id=1)
    }
    return render(request, 'main/metrics.html', context)



def metricsupdate(request, pk):
    metrics = Metric.objects.get(id=pk)
    form = MetricsForm(instance=metrics)
    context = {
        'title': 'Update Metrics',
        'form': form
    }
    if request.method == 'POST':
        form = MetricsForm(request.POST, instance=metrics)
        if form.is_valid():
            form.save()
            sweetify.toast(request, 'Metrics updated successfully')
            return HttpResponseRedirect(reverse('metrics'))
    return render(request, 'main/metricsupdate.html', context)

@login_required(login_url='login')
@admin_or_meter_reader_required
def meter_reading(request):
    form = MeterReadingForm()
    if request.method == 'POST':
        form = MeterReadingForm(request.POST)
        if form.is_valid():
            client = form.cleaned_data['client']
            reading = form.cleaned_data['reading']
            
            # Create a new WaterBill instance and assign the current user
            WaterBill.objects.create(
                name=client,
                created_by=request.user,
                meter_consumption=reading,
                status='Pending',
                duedate=datetime.date.today() + datetime.timedelta(days=15),
                penaltydate=datetime.date.today() + datetime.timedelta(days=30)
            )
            
            sweetify.success(request, 'Meter reading submitted successfully.')
            return HttpResponseRedirect(reverse('ongoingbills'))

    context = {
        'title': 'Meter Reading',
        'form': form
    }
    return render(request, 'main/meter_reading.html', context)

@login_required
def client_bill_history(request):
    if request.user.is_superuser:
        return redirect('billshistory')
    
    try:
        client = Client.objects.get(name=request.user)
        bills = WaterBill.objects.filter(name=client).order_by('-created_on')
    except Client.DoesNotExist:
        client = None
        bills = []
        sweetify.error(request, 'No client profile found for your account.')

    context = {
        'title': 'My Billing History',
        'bills': bills,
        'client': client
    }
    return render(request, 'main/client_bill_history.html', context)

@login_required(login_url='login')
@admin_or_meter_reader_required
def manage_billing(request, pk):
    client = Client.objects.get(id=pk)
    now = timezone.now()
    current_month = now.month
    current_year = now.year

    # Check if a bill already exists for the current month
    try:
        bill = WaterBill.objects.filter(name=client, created_on__year=current_year, created_on__month=current_month).order_by('-created_on').first()
    except WaterBill.DoesNotExist:
        bill = None

    if request.method == 'POST':
        form = MeterReadingForm(request.POST, instance=bill)
        if form.is_valid():
            reading = form.cleaned_data['reading']
            
            # Get the previous reading, excluding the current bill if it exists
            previous_bills_qs = WaterBill.objects.filter(name=client).order_by('-created_on')
            if bill: # If we are updating a bill, exclude it from the search for the previous one
                previous_bills_qs = previous_bills_qs.exclude(pk=bill.pk)
            
            previous_bill = previous_bills_qs.first()
            previous_reading = previous_bill.reading if previous_bill else 0
            
            # Calculate consumption
            consumption = reading - previous_reading
            
            # Get the metric for calculation
            metric = Metric.objects.first()
            bill_amount = consumption * metric.consump_amount

            # Create or update the bill
            if bill:
                bill.reading = reading
                bill.meter_consumption = consumption
                bill.save()
                sweetify.success(request, 'Billing information updated successfully.')
            else:
                new_bill = form.save(commit=False)
                new_bill.name = client
                new_bill.created_by = request.user
                new_bill.status = 'Pending'
                new_bill.duedate = now.date() + datetime.timedelta(days=15)
                new_bill.penaltydate = now.date() + datetime.timedelta(days=30)
                new_bill.save()
                sweetify.success(request, 'New meter reading has been recorded.')
            
            return redirect('meter_reader_dashboard')
    else:
        form = MeterReadingForm(instance=bill)

    previous_bill = WaterBill.objects.filter(name=client).order_by('-created_on').first()

    context = {
        'title': 'Manage Billing',
        'client': client,
        'form': form,
        'previous_bill': previous_bill,
        'bill': bill
    }
    return render(request, 'main/manage_billing.html', context)

from django.db.models.functions import TruncMonth

@login_required(login_url='login')
@admin_required
def reports(request):
    paid_bills = WaterBill.objects.filter(status='Paid').order_by('created_on')
    pending_bills = WaterBill.objects.filter(status='Pending')
    
    total_revenue = sum(bill.payable() for bill in paid_bills)
    outstanding_payments = sum(bill.payable() for bill in pending_bills)
    total_consumption = WaterBill.objects.aggregate(total=Sum('meter_consumption'))['total'] or 0

    # Monthly revenue chart data
    monthly_revenue_dict = defaultdict(float)
    for bill in paid_bills:
        month_key = bill.created_on.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_revenue_dict[month_key] += bill.payable()
    monthly_revenue = [{'month': month, 'total': total} for month, total in sorted(monthly_revenue_dict.items())]

    # Billing status chart data
    paid_bills_count = paid_bills.count()
    pending_bills_count = pending_bills.count()

    context = {
        'title': 'Reports',
        'total_revenue': total_revenue,
        'outstanding_payments': outstanding_payments,
        'total_consumption': total_consumption,
        'monthly_revenue': monthly_revenue,
        'paid_bills_count': paid_bills_count,
        'pending_bills_count': pending_bills_count,
    }
    return render(request, 'main/reports.html', context)


@login_required
@client_facing_login_required
def initiate_mpesa_payment(request, bill_id):
    try:
        bill = WaterBill.objects.get(id=bill_id, name__name=request.user)
    except WaterBill.DoesNotExist:
        sweetify.error(request, 'Bill not found.')
        return redirect('client_bill_history')

    if bill.status == 'Paid':
        sweetify.info(request, 'This bill has already been paid.')
        return redirect('client_bill_history')

    amount = int(bill.payable())
    phone_number = request.user.phone_number

    if not phone_number:
        sweetify.error(request, 'Please update your profile with a valid phone number.')
        return redirect('profile', pk=request.user.pk)

    response_data = initiate_stk_push(phone_number, amount, 'Water Bill Payment', f'Bill {bill.id}')

    if response_data and response_data.get('ResponseCode') == '0':
        bill.checkout_request_id = response_data.get('CheckoutRequestID')
        bill.save()
        sweetify.success(request, 'STK push initiated. Please enter your M-Pesa PIN on your phone to complete the payment.')
    else:
        error_message = response_data.get('errorMessage', 'Failed to initiate STK push.') if response_data else 'Failed to initiate STK push.'
        sweetify.error(request, error_message)
    
    return redirect('client_bill_history')


@csrf_exempt
@require_POST
def mpesa_callback(request):
    payload = json.loads(request.body)
    checkout_request_id = payload.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
    result_code = payload.get('Body', {}).get('stkCallback', {}).get('ResultCode')

    if checkout_request_id and result_code == 0:
        try:
            bill = WaterBill.objects.get(checkout_request_id=checkout_request_id)
            bill.status = 'Paid'
            bill.save()
        except WaterBill.DoesNotExist:
            pass
    return HttpResponse(status=200)


@login_required(login_url='login')
@admin_required
def register_customer(request):
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Automatically create a client profile for the new customer
            Client.objects.create(
                name=user,
                first_name=form.cleaned_data.get('first_name'),
                last_name=form.cleaned_data.get('last_name'),
                contact_number=form.cleaned_data.get('phone_number'),
                address=form.cleaned_data.get('address', 'N/A'),
                status='Pending' # Or whatever default status is appropriate
            )
            sweetify.success(request, 'Customer registered and client profile created successfully!')
            return redirect('users')
        else:
            sweetify.error(request, 'Please correct the errors below.')
    else:
        form = CustomerRegistrationForm()
    
    context = {
        'title': 'Register Customer',
        'form': form
    }
    return render(request, 'account/register.html', context)



@login_required
def initiate_mpesa_payment(request, bill_id):
    try:
        bill = WaterBill.objects.get(id=bill_id, name__name=request.user)
    except WaterBill.DoesNotExist:
        sweetify.error(request, 'Bill not found.')
        return redirect('ongoingbills')

    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        if not phone_number:
            sweetify.error(request, 'Phone number is required.')
            return redirect('ongoingbills')

        amount = int(bill.payable)
        account_reference = f'BILL{bill.id}'
        transaction_desc = f'Payment for bill {bill.id}'
        callback_url = request.build_absolute_uri(reverse('mpesa_callback'))

        response = initiate_stk_push(phone_number, amount, account_reference, transaction_desc, callback_url)

        if response and response.get('ResponseCode') == '0':
            bill.checkout_request_id = response['CheckoutRequestID']
            bill.save()
            sweetify.success(request, 'STK push initiated successfully. Please check your phone.')
        else:
            sweetify.error(request, 'Failed to initiate STK push. Please try again.')

        return redirect('ongoingbills')

    context = {
        'title': 'Pay with M-Pesa',
        'bill': bill
    }
    return render(request, 'main/pay_with_mpesa.html', context)


@csrf_exempt
def mpesa_callback(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        if data['Body']['stkCallback']['ResultCode'] == 0:
            checkout_request_id = data['Body']['stkCallback']['CheckoutRequestID']
            try:
                bill = WaterBill.objects.get(checkout_request_id=checkout_request_id)
                bill.status = 'Paid'
                bill.save()
            except WaterBill.DoesNotExist:
                # Handle the case where the bill is not found
                pass

    return HttpResponse(status=200)


@login_required(login_url='login')
@admin_or_meter_reader_required
def register_customer(request):
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            sweetify.success(request, 'Customer has been registered successfully.')
            if request.user.is_superuser:
                return redirect('users')
            else:
                return redirect('meter_reader_dashboard')
    else:
        form = CustomerRegistrationForm()
    
    context = {
        'title': 'Register New Customer',
        'form': form
    }
    return render(request, 'main/register_customer.html', context)

