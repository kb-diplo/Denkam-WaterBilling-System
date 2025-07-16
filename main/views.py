from django.shortcuts import render, redirect, get_object_or_404, HttpResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import update_session_auth_hash
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import datetime
from .forms import BillForm, ClientUpdateForm, ClientForm, MetricsForm, MeterReadingForm
from account.models import *
from .forms import *
from .mpesa_utils import initiate_stk_push
from django.db.models import F, Sum
import sweetify
import json
from account.forms import MeterReaderClientCreationForm
from account.decorators import admin_required, customer_or_admin_required, customer_required, admin_or_meter_reader_required, meter_reader_required
from .decorators import client_facing_login_required
from django.utils import timezone
from collections import defaultdict
import io
from django.http import FileResponse
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors


def landingpage(request):
    return render(request, 'account/landingpage.html')  


@login_required(login_url='login')
@admin_required
def dashboard(request):
    paid_bills_count = WaterBill.objects.filter(status='Paid').count()
    pending_bills_count = WaterBill.objects.filter(status='Pending').count()
    meter_readers_count = Account.objects.filter(role='METER_READER').count()

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
        'meter_readers_count': meter_readers_count,
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
    return render(request, 'account/meter_reader_dashboard.html', context)


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
    if request.user.role == Account.Role.ADMIN:
        ongoing_bills = WaterBill.objects.filter(status='Pending')
    else:
        ongoing_bills = WaterBill.objects.filter(name__name_id=request.user.id, status='Pending')

    context = {
        'title': 'Ongoing Bills',
        'ongoingbills': ongoing_bills,
    }

    return render(request, 'main/billsongoing.html', context)


@login_required(login_url='login')
@customer_or_admin_required
def history_bills(request):
    if request.user.role == Account.Role.ADMIN:
        bills_history = WaterBill.objects.filter(status='Paid')
    else:
        bills_history = WaterBill.objects.filter(name__name=request.user, status='Paid')

    context = {
        'title': 'Bills History',
        'billshistory': bills_history,
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
@admin_required
def users(request):
    # Get all non-admin users who are meter readers
    meter_readers = Account.objects.filter(is_superuser=False, role=Account.Role.METER_READER)
    clients = Account.objects.filter(is_superuser=False, role=Account.Role.CUSTOMER)

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
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            user = Account.objects.create_user(
                first_name=form.cleaned_data.get('first_name'),
                last_name=form.cleaned_data.get('last_name'),
                email=form.cleaned_data.get('email'),
                password=form.cleaned_data.get('password'),
                role='CUSTOMER'
            )
            instance.name = user
            instance.save()
            sweetify.success(request, 'New client has been added.')
            return redirect('clients')
    else:
        form = ClientForm()

    all_clients = Client.objects.all()
    context = {
        'title': 'Clients',
        'clients': all_clients,
        'form': form
    }
    return render(request, 'main/clients.html', context)

@login_required(login_url='login')
@admin_required
def client_delete(request, pk):
    client = get_object_or_404(Client, pk=pk)
    context = {
        'title': 'Delete Client',
        'client': client,
    }
    if request.method == 'POST':
        # The associated user account should also be deleted or handled appropriately
        # For example, if the client is linked to an Account via a OneToOneField named 'user_account'
        if hasattr(client, 'name') and client.name:
            client.name.delete() # This assumes 'name' is the related user account
        client.delete()
        sweetify.success(request, 'Client deleted successfully!')
        return redirect('clients')
    
    return render(request, 'main/clientdelete.html', context)


@login_required(login_url='login')
@admin_required
def client_billing_history(request, pk):
    client = get_object_or_404(Client, id=pk)
    bills = WaterBill.objects.filter(name=client).order_by('-created_on')
    context = {
        'title': f'Billing History - {client.first_name} {client.last_name}',
        'client': client,
        'bills': bills
    }
    return render(request, 'main/client_billing_history.html', context)

@login_required(login_url='login')
@admin_or_meter_reader_required
def client_update(request,pk):
    client = get_object_or_404(Client, id=pk)
    if request.method == 'POST':
        form = ClientUpdateForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            sweetify.success(request, 'Client updated successfully!')
            return redirect('clients')
        else:
            sweetify.error(request, 'Please correct the errors below.')
    else:
        form = ClientUpdateForm(instance=client)

    context = {
        'title': 'Update Client',
        'client': client,
        'form': form
    }
    return render(request, 'main/clientupdate.html', context)



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
    clients = Client.objects.select_related('name').all()
    query = request.GET.get('q')
    if query:
        clients = clients.filter(
            Q(name__first_name__icontains=query) |
            Q(name__last_name__icontains=query) |
            Q(name__email__icontains=query) |
            Q(id__icontains=query)
        ).distinct()

    paginator = Paginator(clients, 10)  # Show 10 clients per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get billed client IDs for the current month
    now = timezone.now()
    billed_client_ids = WaterBill.objects.filter(
        created_on__year=now.year,
        created_on__month=now.month
    ).values_list('name_id', flat=True)

    context = {
        'title': 'Meter Reading - Select Client',
        'page_obj': page_obj,
        'query': query,
        'billed_client_ids': list(billed_client_ids),
    }
    return render(request, 'main/meter_reading.html', context)


@login_required
def client_bill_history(request, pk):
    client = get_object_or_404(Client, id=pk)
    bills = WaterBill.objects.filter(name=client).order_by('-created_on')
    context = {
        'title': f'Billing History for {client.first_name} {client.last_name}',
        'bills': bills,
        'client': client
    }
    return render(request, 'main/client_bill_history.html', context)


@login_required(login_url='login')
@admin_or_meter_reader_required
def add_meter_reading(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    now = timezone.now()
    last_bill = WaterBill.objects.filter(name=client).order_by('-created_on').first()
    last_reading = last_bill.reading if last_bill else 0

    if request.method == 'POST':
        form = MeterReadingForm(request.POST)
        if form.is_valid():
            reading = form.cleaned_data['reading']

            if reading < last_reading:
                sweetify.error(request, f'New reading cannot be less than the previous reading of {last_reading}.')
            else:
                consumption = reading - last_reading
                WaterBill.objects.create(
                    name=client,
                    reading=reading,
                    meter_consumption=consumption,
                    created_by=request.user,
                    status='Pending',
                    duedate=now.date() + datetime.timedelta(days=15),
                    penaltydate=now.date() + datetime.timedelta(days=30)
                )
                sweetify.success(request, 'New meter reading has been recorded.', persistent='OK')
                return redirect('clients')
        else:
            sweetify.error(request, 'Please correct the error below.')
    else:
        form = MeterReadingForm()

    context = {
        'form': form,
        'client': client,
        'title': f'Add Meter Reading for {client.first_name} {client.last_name}',
        'last_reading': last_reading
    }
    return render(request, 'main/add_meter_reading.html', context)


@login_required(login_url='login')
@admin_or_meter_reader_required
def manage_billing(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    bill = WaterBill.objects.filter(name=client).order_by('-created_on').first()

    if not bill:
        sweetify.error(request, 'No billing record found for this client. Please add a new meter reading first.', persistent='OK')
        return redirect('clients')

    # This is the bill before the one we are editing.
    previous_bill = WaterBill.objects.filter(name=client, created_on__lt=bill.created_on).order_by('-created_on').first()
    previous_reading = previous_bill.reading if previous_bill else 0

    if request.method == 'POST':
        form = MeterReadingForm(request.POST)
        if form.is_valid():
            reading = form.cleaned_data['reading']
            if reading < previous_reading:
                sweetify.error(request, f'Current reading cannot be less than the previous reading of {previous_reading}.')
            else:
                consumption = reading - previous_reading
                bill.reading = reading
                bill.meter_consumption = consumption
                bill.save()
                sweetify.success(request, 'Billing information updated successfully.', persistent='OK')
                return redirect('clients')
        else:
             sweetify.error(request, 'Please correct the error below.')
    else:
        form = MeterReadingForm(initial={'reading': bill.reading})

    context = {
        'title': f'Edit Billing for {client.first_name} {client.last_name}',
        'client': client,
        'form': form,
        'bill': bill,
        'previous_bill': previous_bill
    }
    return render(request, 'main/manage_billing.html', context)

from django.db.models.functions import TruncMonth

@login_required(login_url='login')
@admin_required
def reports(request):
    metric = Metric.objects.first()
    consump_amount = metric.consump_amount if metric else 1.0
    penalty_amount = metric.penalty_amount if metric else 0.0

    paid_bills = WaterBill.objects.filter(status='Paid').order_by('created_on')
    pending_bills = WaterBill.objects.filter(status='Pending')

    # Calculate total revenue from paid bills using aggregation
    total_revenue = paid_bills.aggregate(
        total=Sum(F('meter_consumption') * consump_amount)
    )['total'] or 0

    # Calculate outstanding payments from pending bills using aggregation
    outstanding_payments = pending_bills.aggregate(
        total=Sum(F('meter_consumption') * consump_amount)
    )['total'] or 0

    # Add penalties for pending bills due today
    today = timezone.now().date()
    penalty_for_pending = pending_bills.filter(penaltydate=today).count() * penalty_amount
    outstanding_payments += penalty_for_pending

    total_consumption = WaterBill.objects.aggregate(total=Sum('meter_consumption'))['total'] or 0

    # Monthly revenue chart data
    monthly_revenue_dict = defaultdict(float)
    for bill in paid_bills:
        month_key = bill.created_on.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        bill_total = (bill.meter_consumption * consump_amount)
        if bill.penaltydate == bill.created_on.date(): # A simplified assumption for penalty
            bill_total += penalty_amount
        monthly_revenue_dict[month_key] += bill_total
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
@admin_required
def payment_records(request):
    payments = MpesaPayment.objects.all().order_by('-created_on')
    context = {
        'title': 'M-Pesa Payment Records',
        'payments': payments,
    }
    return render(request, 'main/payment_records.html', context)


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
    try:
        payload = json.loads(request.body)
        stk_callback = payload.get('Body', {}).get('stkCallback', {})
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        result_code = stk_callback.get('ResultCode')
        result_desc = stk_callback.get('ResultDesc')

        if not checkout_request_id:
            return HttpResponse(status=400) # Bad request if no checkout ID

        # Log the entire callback
        MpesaPayment.objects.create(
            checkout_request_id=checkout_request_id,
            result_code=result_code,
            result_desc=result_desc,
        )

        if str(result_code) == '0':
            callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
            amount = next((item['Value'] for item in callback_metadata if item['Name'] == 'Amount'), None)
            transaction_id = next((item['Value'] for item in callback_metadata if item['Name'] == 'MpesaReceiptNumber'), None)
            phone_number = next((item['Value'] for item in callback_metadata if item['Name'] == 'PhoneNumber'), None)

            try:
                bill = WaterBill.objects.get(checkout_request_id=checkout_request_id)
                bill.status = 'Paid'
                bill.save()

                # Update the payment log with bill details
                payment = MpesaPayment.objects.get(checkout_request_id=checkout_request_id)
                payment.bill = bill
                payment.transaction_id = transaction_id
                payment.amount = amount
                payment.phone_number = phone_number
                payment.save()

            except WaterBill.DoesNotExist:
                # Handle case where bill is not found but payment was made
                pass

    except json.JSONDecodeError:
        return HttpResponse(status=400) # Invalid JSON
    except Exception as e:
        # Log unexpected errors
        return HttpResponse(status=500)

    return HttpResponse(status=200)


@login_required(login_url='login')
@admin_or_meter_reader_required
def register_customer(request):
    if request.method == 'POST':
        form = MeterReaderClientCreationForm(request.POST)
        if form.is_valid():
            # Create the user account
            user = Account.objects.create_user(
                email=form.cleaned_data['email'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                password=form.cleaned_data['password']
            )
            user.role = Account.Role.CUSTOMER # Set role to Customer
            user.save()

            # Create the associated client profile
            Client.objects.create(
                name=user,
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                contact_number=form.cleaned_data['contact_number'],
                address=form.cleaned_data['address'],
                status='Pending'
            )
            
            sweetify.success(request, 'New client has been registered successfully!')
            # Redirect based on user role
            if request.user.role == 'METER_READER':
                return redirect('meter_reader_dashboard')
            else:
                return redirect('users') # For admins
        else:
            sweetify.error(request, 'Please correct the errors below.')
    else:
        form = MeterReaderClientCreationForm()
    
    context = {
        'title': 'Register New Client',
        'form': form
    }
    return render(request, 'account/admin_register_user.html', context)









@login_required
def generate_bill_pdf(request, bill_id):
    try:
        bill = WaterBill.objects.get(id=bill_id)
        # Ensure the user has permission to view this bill
        is_owner = (request.user.role == Account.Role.CUSTOMER and bill.name.name == request.user)
        is_admin = (request.user.role == Account.Role.ADMIN)
        
        if not (is_owner or is_admin):
            return HttpResponse("Unauthorized", status=403)

    except WaterBill.DoesNotExist:
        return HttpResponse("Bill not found", status=404)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter, bottomup=0)
    textob = c.beginText()
    textob.setTextOrigin(inch, inch)
    textob.setFont("Helvetica", 14)

    # Add content to the PDF
    textob.textLine("Denkam Water Billing System")
    textob.textLine("-" * 50)
    textob.textLine(f"Bill ID: {bill.id}")
    textob.textLine(f"Client: {bill.name.name.get_full_name()}")
    textob.textLine(f"Date: {bill.created_on.strftime('%Y-%m-%d')}")
    textob.textLine(f"Status: {bill.status}")
    textob.textLine("-" * 50)
    
    # Calculate previous reading safely
    previous_reading = 0
    if bill.meter_consumption is not None and bill.reading is not None:
        previous_reading = bill.reading - bill.meter_consumption

    textob.textLine(f"Previous Reading: {previous_reading}")
    textob.textLine(f"Current Reading: {bill.reading or 0}")
    textob.textLine(f"Consumption (m³): {bill.meter_consumption or 0}")
    textob.textLine(" ")
    textob.textLine(f"Amount Payable: KES {bill.payable()}")

    c.drawText(textob)
    c.showPage()
    c.save()
    buf.seek(0)

    return FileResponse(buf, as_attachment=True, filename=f'bill_{bill.id}.pdf')


@login_required
@admin_required
def generate_client_list_pdf(request):
    clients = Client.objects.select_related('name').all()
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph("Denkam Water Billing System - Client List", styles['h1'])
    elements.append(title)
    
    # Table Data
    data = [['ID', 'Full Name', 'Email', 'Contact', 'Address', 'Status']]
    for client in clients:
        data.append([
            client.id,
            client.name.get_full_name(),
            client.name.email,
            client.contact_number,
            client.address,
            client.status
        ])
        
    # Create Table
    table = Table(data)
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ])
    table.setStyle(style)
    
    elements.append(table)
    
    doc.build(elements)
    
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename='client_list.pdf')

