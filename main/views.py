from django.shortcuts import render, redirect, get_object_or_404, HttpResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import update_session_auth_hash
from account.models import Account
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import datetime
from .forms import BillForm, ClientUpdateForm, ClientForm, MetricsForm, MeterReadingForm
from account.models import *
from .forms import *
from .mpesa_utils import initiate_stk_push
from django.db.models import F, Sum, Q
import sweetify
import json
from account.forms import MeterReaderClientCreationForm
from account.decorators import admin_required, customer_required, meter_reader_required, admin_or_meter_reader_required, customer_or_admin_required, meter_reader_required
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
        'ongoingbills': WaterBill.objects.filter(status='Pending', name__isnull=False),
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
        ongoing_bills = WaterBill.objects.filter(status='Pending', name__isnull=False)
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
        bills_history = WaterBill.objects.filter(status__in=['Paid', 'Partially Paid']).prefetch_related('cash_payments', 'mpesa_payments')
    else:
        bills_history = WaterBill.objects.filter(name__name=request.user, status__in=['Paid', 'Partially Paid']).prefetch_related('cash_payments', 'mpesa_payments')

    # Add payment method info to each bill
    for bill in bills_history:
        bill.payment_method = None
        bill.payment_reference = None
        
        # Check for cash payments first
        cash_payment = bill.cash_payments.first()
        if cash_payment:
            bill.payment_method = 'Cash'
            bill.payment_reference = cash_payment.reference_id
        
        # Check for M-Pesa payments (might override cash if both exist)
        mpesa_payment = bill.mpesa_payments.filter(result_code=0).first()  # Only successful M-Pesa payments
        if mpesa_payment:
            bill.payment_method = 'M-Pesa'
            bill.payment_reference = mpesa_payment.transaction_id
        
        # If no payment method found, set default
        if not bill.payment_method:
            bill.payment_method = 'Unknown'
            bill.payment_reference = 'No Reference'

    context = {
        'title': 'Bills History',
        'billshistory': bills_history,
    }
    return render(request, 'main/billshistory.html', context)


@login_required(login_url='login')
@customer_or_admin_required
def download_billing_history(request):
    """Download billing history as PDF"""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import inch
    import io
    
    # Get bills data
    if request.user.role == Account.Role.ADMIN:
        bills_history = WaterBill.objects.filter(status__in=['Paid', 'Partially Paid']).prefetch_related('cash_payments', 'mpesa_payments').order_by('-created_on')
    else:
        bills_history = WaterBill.objects.filter(name__name=request.user, status__in=['Paid', 'Partially Paid']).prefetch_related('cash_payments', 'mpesa_payments').order_by('-created_on')
    
    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=0.5*inch)
    elements = []
    
    # Title
    styles = getSampleStyleSheet()
    title = Paragraph("<b>Denkam Waters - Billing History Report</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 0.2*inch))
    
    # Prepare table data
    data = [[
        'Client Name', 'Consumption (m³)', 'Amount (KSh)', 'Due Date', 
        'Status', 'Payment Method', 'Reference', 'Date Paid'
    ]]
    
    for bill in bills_history:
        # Get payment method info
        payment_method = 'Unknown'
        payment_reference = 'No Reference'
        
        cash_payment = bill.cash_payments.first()
        if cash_payment:
            payment_method = 'Cash'
            payment_reference = cash_payment.reference_id
        
        mpesa_payment = bill.mpesa_payments.filter(result_code=0).first()
        if mpesa_payment:
            payment_method = 'M-Pesa'
            payment_reference = mpesa_payment.transaction_id or 'No ID'
        
        data.append([
            str(bill.name),
            f"{bill.meter_consumption or 0} m³",
            f"KSh{bill.payable}",
            bill.duedate.strftime('%Y-%m-%d') if bill.duedate else 'N/A',
            bill.status,
            payment_method,
            payment_reference,
            bill.created_on.strftime('%Y-%m-%d') if bill.created_on else 'N/A'
        ])
    
    # Create table
    table = Table(data, colWidths=[1.2*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 1*inch, 0.8*inch])
    
    # Style the table
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ])
    
    table.setStyle(style)
    elements.append(table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="billing_history.pdf"'
    return response

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
                client = client_form.save(commit=False)
                # Sync the client fields with account fields for consistency
                client.first_name = user.first_name
                client.last_name = user.last_name
                client.save()
                print(f"Client updated: {client.first_name} {client.last_name}")
            
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



@login_required(login_url='login')
@admin_required
def metrics(request):
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to view this page.")
        return redirect('home')
    
    # Get or create metric record
    metric, created = Metric.objects.get_or_create(pk=1, defaults={'consump_amount': 0, 'penalty_amount': 0})
    
    if request.method == 'POST':
        form = MetricsForm(request.POST, instance=metric)
        if form.is_valid():
            form.save()
            messages.success(request, 'Rates updated successfully.')
            return redirect('metrics')
    else:
        form = MetricsForm(instance=metric)
    
    context = {
        'title': 'Billing Rates Management',
        'form': form,
        'metric': metric,
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


@login_required
@admin_or_meter_reader_required
def delete_bill(request, bill_id):
    bill = get_object_or_404(WaterBill, id=bill_id)
    client_id = bill.name.id
    bill.delete()
    sweetify.success(request, 'Bill deleted successfully!', persistent='OK')
    return redirect('client_billing_history', pk=client_id)


@login_required(login_url='login')
@customer_or_admin_required
def history_bills(request):
    if request.user.role == Account.Role.ADMIN:
        bills = WaterBill.objects.all().order_by('-created_on')
    else:
        bills = WaterBill.objects.filter(name__name_id=request.user.id).order_by('-created_on')

    context = {
        'title': 'Billing History',
        'bills': bills,
    }
    return render(request, 'main/history_bills.html', context)


@login_required(login_url='login')
@admin_or_meter_reader_required
def add_meter_reading(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    now = timezone.now()
    last_bill = WaterBill.objects.filter(name=client).order_by('-created_on').first()
    last_reading = last_bill.reading if last_bill and last_bill.reading is not None else 0

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
    previous_reading = previous_bill.reading if previous_bill and previous_bill.reading is not None else 0

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
from django.utils import timezone
from datetime import datetime, timedelta
from collections import defaultdict
import json
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa

@login_required(login_url='login')
@admin_required
def reports(request):
    # Get the current date and time for the report
    now = timezone.now()
    
    # Get the selected period from the request (default to 'month' if not provided)
    period = request.GET.get('period', 'month')
    
    # Initialize date range
    start_date = None
    end_date = None
    
    # Set the date range based on the selected period
    if period == 'today':
        start_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = timezone.now()
        period_label = f"Today's Report ({start_date.strftime('%b %d, %Y')})"
    elif period == 'week':
        start_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=timezone.now().weekday())
        end_date = timezone.now()
        period_label = f"Weekly Report ({start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')})"
    elif period == 'month':
        start_date = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = timezone.now()
        period_label = f"Monthly Report ({start_date.strftime('%B %Y')})"
    elif period == 'year':
        start_date = timezone.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = timezone.now()
        period_label = f"Yearly Report ({start_date.year})"
    elif period == 'custom':
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        
        try:
            if start_date_str and end_date_str:
                start_date = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
                end_date = timezone.make_aware(datetime.strptime(end_date_str, '%Y-%m-%d')) + timedelta(days=1) - timedelta(seconds=1)
                period_label = f"Custom Report ({start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')})"
            else:
                # Default to current month if custom dates are not provided
                start_date = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                end_date = timezone.now()
                period_label = f"Monthly Report ({start_date.strftime('%B %Y')})"
        except (ValueError, TypeError):
            # Handle invalid date format
            start_date = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = timezone.now()
            period_label = f"Monthly Report ({start_date.strftime('%B %Y')})"
    
    # Get all bills within the date range
    bills = WaterBill.objects.filter(created_on__range=[start_date, end_date])
    
    # Calculate total billed amount (sum of all bills' payable amounts)
    total_billed = sum(bill.payable() for bill in bills if bill.payable() is not None)
    
    # Get all payments within the date range
    cash_payments = CashPayment.objects.filter(payment_date__range=[start_date, end_date])
    mpesa_payments = MpesaPayment.objects.filter(created_at__range=[start_date, end_date])
    
    # Calculate total collected (sum of all payments)
    total_cash = cash_payments.aggregate(total=Sum('amount_paid'))['total'] or 0
    total_mpesa = mpesa_payments.aggregate(total=Sum('amount'))['total'] or 0
    total_collected = total_cash + total_mpesa
    
    # Calculate outstanding balance
    outstanding_balance = total_billed - total_collected
    
    # Calculate collection rate (percentage of billed amount that has been collected)
    collection_rate = (total_collected / total_billed * 100) if total_billed > 0 else 0
    
    # Get monthly revenue data for the chart
    monthly_revenue_data = []
    monthly_totals = defaultdict(float)
    
    # Add cash payments to monthly totals
    for payment in cash_payments:
        month_key = payment.payment_date.strftime('%Y-%m')
        monthly_totals[month_key] += float(payment.amount_paid or 0)
    
    # Add M-Pesa payments to monthly totals
    for payment in mpesa_payments:
        month_key = payment.created_at.strftime('%Y-%m')
        monthly_totals[month_key] += float(payment.amount or 0)
    
    # Convert to list of dictionaries for the template
    monthly_revenue_data = [{'month': month, 'total': total} 
                          for month, total in sorted(monthly_totals.items())]
    
    # Format monthly revenue for chart
    monthly_revenue = [{'month': m['month'], 'total': float(m['total'])} 
                      for m in monthly_revenue_data]

    # Billing status counts
    paid_bills_count = bills.filter(status='Paid').count()
    pending_bills_count = bills.filter(status='Pending').count()
    partially_paid_count = bills.filter(status='Partially Paid').count()
    
    # Total customers
    total_customers = Account.objects.filter(role=Account.Role.CUSTOMER).count()
    
    # Prepare context with proper defaults and ensure all required fields are present
    context = {
        'title': 'Billing Reports',
        'period_label': period_label or 'Report',
        'start_date': start_date or now,
        'end_date': end_date or now,
        'now': now,
        'period': period or 'month',
        'total_billed': float(total_billed or 0),
        'total_collected': float(total_collected or 0),
        'outstanding_balance': float(outstanding_balance or 0),
        'collection_rate': float(collection_rate or 0),
        'monthly_revenue': json.dumps(monthly_revenue or []),
        'monthly_revenue_data': monthly_revenue_data or [],
        'paid_bills_count': int(paid_bills_count or 0),
        'pending_bills_count': int(pending_bills_count or 0),
        'partially_paid_count': int(partially_paid_count or 0),
        'total_customers': int(total_customers or 0),
        'cash_payments': list(cash_payments.order_by('-payment_date')) if cash_payments.exists() else [],
        'mpesa_payments': list(mpesa_payments.order_by('-created_at')) if mpesa_payments.exists() else [],
        'cash_payments_count': int(cash_payments.count() if cash_payments else 0),
        'mpesa_payments_count': int(mpesa_payments.count() if mpesa_payments else 0),
    }
    
    return render(request, 'main/reports.html', context)


def generate_pdf_report(context):
    """Generate a PDF report from the reports data"""
    try:
        print("Starting PDF generation...")
        print(f"Context keys: {list(context.keys())}")
        
        # Ensure we have proper iterables for payments with detailed logging
        if 'cash_payments' not in context or context['cash_payments'] is None:
            print("Setting empty cash_payments list")
            context['cash_payments'] = []
        else:
            print(f"Cash payments type: {type(context['cash_payments'])}")
            print(f"Cash payments length: {len(context['cash_payments']) if hasattr(context['cash_payments'], '__len__') else 'N/A'}")
            
        if 'mpesa_payments' not in context or context['mpesa_payments'] is None:
            print("Setting empty mpesa_payments list")
            context['mpesa_payments'] = []
        else:
            print(f"Mpesa payments type: {type(context['mpesa_payments'])}")
            print(f"Mpesa payments length: {len(context['mpesa_payments']) if hasattr(context['mpesa_payments'], '__len__') else 'N/A'}")
        
        # Ensure we have default values for other required fields
        defaults = {
            'total_billed': 0,
            'total_collected': 0,
            'outstanding_balance': 0,
            'total_customers': 0,
            'paid_bills_count': 0,
            'partially_paid_count': 0,
            'pending_bills_count': 0,
            'period_label': 'Report',
            'monthly_revenue': '[]',
            'monthly_revenue_data': [],
            'now': timezone.now()
        }
        
        for key, default in defaults.items():
            if key not in context or context[key] is None:
                print(f"Setting default for {key}: {default}")
                context[key] = default
        
        # Convert any querysets to lists to prevent database access during template rendering
        if hasattr(context['cash_payments'], '_result_cache'):
            context['cash_payments'] = list(context['cash_payments'])
        if hasattr(context['mpesa_payments'], '_result_cache'):
            context['mpesa_payments'] = list(context['mpesa_payments'])
        
        print("Rendering template...")
        template_path = 'main/reports_pdf.html'
        template = get_template(template_path)
        
        # Create a safe copy of context with only serializable data
        safe_context = {}
        for key, value in context.items():
            try:
                # Try to serialize the value to ensure it's safe
                json.dumps(value)
                safe_context[key] = value
            except (TypeError, OverflowError):
                # If not serializable, convert to string
                safe_context[key] = str(value)
        
        html = template.render(safe_context)
        print("Template rendered successfully")
        
        # Create PDF
        response = HttpResponse(content_type='application/pdf')
        filename = f"denkam_water_report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        print("Generating PDF...")
        # Generate PDF with additional options
        pisa_status = pisa.CreatePDF(
            html,
            dest=response,
            encoding='utf-8',
            link_callback=None,
            show_error_as_pdf=True
        )
        
        if pisa_status.err:
            error_msg = f"PDF Generation Error: {pisa_status.err}"
            print(error_msg)
            return HttpResponse('Error generating PDF. Please try again later.', status=500)
        
        print("PDF generated successfully")
        return response
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        error_msg = f"PDF Generation Error: {str(e)}\n\nTraceback:\n{error_trace}"
        print(error_msg)
        return HttpResponse(f'Error generating PDF: {str(e)}', status=500)


@login_required
@customer_or_admin_required
def view_receipt(request, bill_id):
    bill = get_object_or_404(WaterBill, id=bill_id)
    cash_payments = bill.cash_payments.all().order_by('payment_date')
    mpesa_payments = bill.mpesa_payments.all().order_by('created_on')

    # Ensure only the client or an admin can view the receipt
    if request.user.role == Account.Role.CUSTOMER and bill.name.name != request.user:
        sweetify.error(request, 'You are not authorized to view this receipt.')
        return redirect('history_bills')

    context = {
        'title': f'Receipt for Bill #{bill.id}',
        'bill': bill,
        'cash_payments': cash_payments,
        'mpesa_payments': mpesa_payments,
    }
    return render(request, 'main/receipt.html', context)


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


@login_required
@admin_or_meter_reader_required
def admin_send_stk_push(request, bill_id):
    try:
        bill = WaterBill.objects.get(id=bill_id)
    except WaterBill.DoesNotExist:
        sweetify.error(request, 'Bill not found.')
        return redirect('manage_billing')

    if bill.status == 'Paid':
        sweetify.info(request, 'This bill has already been paid.')
        return redirect('manage_billing')

    client = bill.name
    amount = int(bill.payable())
    phone_number = client.phone_number

    if not phone_number:
        sweetify.error(request, f'Client {client.first_name} {client.last_name} does not have a phone number in their profile.')
        return redirect('manage_billing')

    # Assuming initiate_stk_push is imported from your mpesa utilities
    response_data = initiate_stk_push(phone_number, amount, 'Water Bill Payment', f'Bill {bill.id}')

    if response_data and response_data.get('ResponseCode') == '0':
        bill.checkout_request_id = response_data.get('CheckoutRequestID')
        bill.save()
        sweetify.success(request, f'STK push sent to {client.first_name} {client.last_name} ({phone_number}).')
    else:
        error_message = response_data.get('errorMessage', 'Failed to initiate STK push.') if response_data else 'Failed to initiate STK push.'
        sweetify.error(request, error_message)
    
    return redirect('manage_billing')


@login_required
@admin_or_meter_reader_required
def generate_bills(request):
    if request.method == 'POST':
        # In a real-world scenario, this should be a background task.
        active_clients = Client.objects.filter(status='Active')
        now = timezone.now()
        bills_created = 0

        for client in active_clients:
            last_bill = WaterBill.objects.filter(name=client).order_by('-created_on').first()
            if not last_bill or last_bill.created_on.month != now.month:
                # This is a simplified logic. A real system would need more robust checks.
                # For now, we assume a bill is generated if one doesn't exist for the current month.
                WaterBill.objects.create(
                    name=client,
                    reading=last_bill.reading if last_bill else 0,
                    meter_consumption=0,  # This should be calculated based on new readings
                    created_by=request.user,
                    status='Pending',
                    duedate=now.date() + datetime.timedelta(days=15),
                    penaltydate=now.date() + datetime.timedelta(days=30)
                )
                bills_created += 1
        
        sweetify.success(request, f'{bills_created} bills have been generated successfully.')
        return redirect('ongoing_bills')

    context = {
        'title': 'Generate Monthly Bills',
    }
    return render(request, 'main/generate_bills.html', context)


@login_required
@admin_or_meter_reader_required
def select_client_for_payment(request):
    clients_with_pending_bills = Client.objects.filter(waterbill__status='Pending').distinct()
    query = request.GET.get('q')
    if query:
        clients_with_pending_bills = clients_with_pending_bills.filter(
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query) | 
            Q(account_number__icontains=query)
        ).distinct()

    context = {
        'title': 'Record Cash Payment',
        'clients': clients_with_pending_bills,
    }
    return render(request, 'main/select_client_for_payment.html', context)


from decimal import Decimal

@login_required
@admin_or_meter_reader_required
def record_cash_payment(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    pending_bills = WaterBill.objects.filter(name=client, status='Pending').order_by('-created_on')

    if request.method == 'POST':
        bill_id = request.POST.get('bill_id')
        amount_paid_str = request.POST.get('amount_paid')

        if not amount_paid_str:
            sweetify.error(request, 'Please enter a valid amount.')
            return redirect('record_cash_payment', client_id=client_id)

        try:
            amount_paid = Decimal(amount_paid_str)
            if amount_paid <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            sweetify.error(request, 'Invalid amount entered. Please enter a positive number.')
            return redirect('record_cash_payment', client_id=client_id)

        bill_to_pay = get_object_or_404(WaterBill, id=bill_id, name=client)

        # Create a cash payment record
        CashPayment.objects.create(
            bill=bill_to_pay,
            amount_paid=amount_paid,
            recorded_by=request.user
        )

        # Check if the bill is fully paid
        total_paid = bill_to_pay.total_cash_paid() + bill_to_pay.mpesa_payments.aggregate(total=models.Sum('amount'))['total'] or 0
        if total_paid >= bill_to_pay.payable():
            bill_to_pay.status = 'Paid'
            bill_to_pay.paid_on = timezone.now()
            bill_to_pay.payment_method = 'Mixed' if bill_to_pay.mpesa_payments.exists() else 'Cash'
            bill_to_pay.save()
            sweetify.success(request, f'Payment for bill {bill_to_pay.id} has been recorded and the bill is now fully paid.')
        else:
            sweetify.info(request, f'Partial payment of KSh {amount_paid} for bill {bill_to_pay.id} has been recorded.')

        return redirect('select_client_for_payment')

    context = {
        'title': f'Record Payment for {client.first_name} {client.last_name}',
        'client': client,
        'pending_bills': pending_bills,
    }
    return render(request, 'main/record_cash_payment.html', context)


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
        # Handle cases where client.name might be None
        if client.name:
            full_name = client.name.get_full_name()
            email = client.name.email
        else:
            # Use client's own fields if no associated account
            full_name = f"{client.first_name or ''} {client.last_name or ''}" if client.first_name or client.last_name else "No Name"
            email = "No Email"
        
        data.append([
            client.id,
            full_name,
            email,
            client.contact_number or "No Contact",
            client.address or "No Address",
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


@login_required
@admin_or_meter_reader_required
def select_payment_method(request, bill_id):
    """View to select payment method (Cash or M-Pesa) for a specific bill"""
    bill = get_object_or_404(WaterBill, id=bill_id)
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        
        if payment_method == 'cash':
            return redirect('record_cash_payment_for_bill', bill_id=bill_id)
        elif payment_method == 'mpesa':
            return redirect('initiate_mpesa_payment', bill_id=bill_id)
        else:
            sweetify.error(request, 'Please select a valid payment method.')
    
    context = {
        'title': f'Select Payment Method for {bill.name}',
        'bill': bill,
    }
    return render(request, 'main/select_payment_method.html', context)


@login_required
@admin_or_meter_reader_required
def record_cash_payment_for_bill(request, bill_id):
    """Record cash payment for a specific bill"""
    bill = get_object_or_404(WaterBill, id=bill_id)
    
    if request.method == 'POST':
        amount_paid_str = request.POST.get('amount_paid')
        
        if not amount_paid_str:
            sweetify.error(request, 'Please enter a valid amount.')
            return redirect('record_cash_payment_for_bill', bill_id=bill_id)
        
        try:
            amount_paid = Decimal(amount_paid_str)
            if amount_paid <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            sweetify.error(request, 'Please enter a valid positive amount.')
            return redirect('record_cash_payment_for_bill', bill_id=bill_id)
        
        # Calculate total amount due
        amount_due = Decimal(str(bill.payable))
        
        # Create cash payment record
        CashPayment.objects.create(
            bill=bill,
            amount_paid=amount_paid,
            recorded_by=request.user
        )
        
        # Update bill status based on actual payment records
        new_status = bill.update_status_based_on_payments()
        
        # Provide appropriate feedback
        if new_status == 'Paid':
            sweetify.success(request, f'Full payment of KSh{amount_paid} recorded successfully for {bill.name}. Bill is now fully paid.')
        else:
            remaining = bill.balance_due
            sweetify.warning(request, f'Partial payment of KSh{amount_paid} recorded. Remaining balance: KSh{remaining:.2f}')
        return redirect('ongoing_bills')
    
    context = {
        'title': f'Record Cash Payment for {bill.name}',
        'bill': bill,
    }
    return render(request, 'main/record_cash_payment_for_bill.html', context)


@login_required
@admin_required
def unified_billing_management(request):
    """Unified billing management - generate bills and manage payments"""
    
    # Get all clients with their latest bills
    clients = Client.objects.filter(status='Connected').prefetch_related('waterbill_set')
    
    billing_data = []
    for client in clients:
        latest_bill = client.waterbill_set.order_by('-created_on').first()
        
        billing_data.append({
            'client': client,
            'latest_bill': latest_bill,
            'has_pending_bill': latest_bill and latest_bill.status in ['Pending', 'Partially Paid'],
            'needs_new_bill': not latest_bill or latest_bill.status == 'Paid',
            'last_reading': latest_bill.reading if latest_bill else 0,
        })
    
    # Handle bill generation
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'generate_bills':
            generated_count = 0
            now = timezone.now()
            
            for client in clients:
                last_bill = client.waterbill_set.order_by('-created_on').first()
                
                # Only generate if no pending bill exists
                if not last_bill or last_bill.status == 'Paid':
                    # For demo purposes, use last reading + 10 as new reading
                    # In real implementation, this would come from meter readings
                    previous_reading = last_bill.reading if last_bill else 0
                    new_reading = previous_reading + 10  # Demo increment
                    consumption = new_reading - previous_reading
                    
                    WaterBill.objects.create(
                        name=client,
                        reading=new_reading,
                        meter_consumption=consumption,
                        created_by=request.user,
                        status='Pending',
                        duedate=now.date() + datetime.timedelta(days=15),
                        penaltydate=now.date() + datetime.timedelta(days=30)
                    )
                    generated_count += 1
            
            sweetify.success(request, f'Generated {generated_count} new bills successfully!')
            return redirect('unified_billing_management')
    
    context = {
        'title': 'Billing Management',
        'billing_data': billing_data,
        'total_clients': len(billing_data),
        'pending_bills': sum(1 for data in billing_data if data['has_pending_bill']),
        'clients_needing_bills': sum(1 for data in billing_data if data['needs_new_bill']),
    }
    
    return render(request, 'main/unified_billing_management.html', context)


@login_required
@admin_required
def generate_bills(request):
    """Generate bills for all clients who need them"""
    
    if request.method == 'POST':
        # Get all connected clients
        clients = Client.objects.filter(status='Connected')
        bills_generated = 0
        
        for client in clients:
            # Check if client already has a pending bill
            existing_pending_bill = WaterBill.objects.filter(
                name=client, 
                status__in=['Pending', 'Partially Paid']
            ).first()
            
            if existing_pending_bill:
                continue  # Skip if already has pending bill
            
            # Get the latest bill to determine last reading
            last_bill = WaterBill.objects.filter(name=client).order_by('-created_on').first()
            last_reading = last_bill.reading if last_bill and last_bill.reading is not None else 0
            
            # For now, we'll create bills with the same reading (no consumption)
            # In practice, you would get new meter readings first
            current_reading = last_reading  # This should be updated with actual new readings
            consumption = current_reading - last_reading
            
            # Create new bill
            now = timezone.now()
            WaterBill.objects.create(
                name=client,
                reading=current_reading,
                meter_consumption=consumption,
                created_by=request.user,
                status='Pending',
                duedate=now.date() + datetime.timedelta(days=15),
                penaltydate=now.date() + datetime.timedelta(days=30)
            )
            bills_generated += 1
        
        if bills_generated > 0:
            sweetify.success(request, f'Successfully generated {bills_generated} bills.', persistent='OK')
        else:
            sweetify.info(request, 'No new bills needed to be generated. All clients already have pending bills.', persistent='OK')
        
        return redirect('ongoing_bills')
    
    # GET request - show the generate bills page
    clients = Client.objects.filter(status='Connected')
    clients_needing_bills = []
    
    for client in clients:
        # Check if client needs a new bill
        has_pending_bill = WaterBill.objects.filter(
            name=client, 
            status__in=['Pending', 'Partially Paid']
        ).exists()
        
        if not has_pending_bill:
            last_bill = WaterBill.objects.filter(name=client).order_by('-created_on').first()
            clients_needing_bills.append({
                'client': client,
                'last_bill': last_bill,
                'last_reading': last_bill.reading if last_bill else 0
            })
    
    context = {
        'title': 'Generate Bills',
        'clients_needing_bills': clients_needing_bills,
        'total_clients': len(clients_needing_bills)
    }
    
    return render(request, 'main/generate_bills.html', context)


@login_required
@customer_or_admin_required
def view_receipt(request, bill_id):
    """View receipt for a specific bill"""
    bill = get_object_or_404(WaterBill, id=bill_id)
    
    # Get payment information
    cash_payments = bill.cash_payments.all().order_by('payment_date')
    mpesa_payments = bill.mpesa_payments.filter(result_code=0).order_by('created_at')
    
    # Ensure only the client or an admin can view the receipt
    if request.user.role == Account.Role.CUSTOMER and bill.name.name != request.user:
        sweetify.error(request, 'You are not authorized to view this receipt.')
        return redirect('history_bills')
    
    context = {
        'title': f'Receipt for Bill #{bill.id}',
        'bill': bill,
        'cash_payments': cash_payments,
        'mpesa_payments': mpesa_payments,
    }
    return render(request, 'main/receipt.html', context)
@admin_required
def generate_bill_pdf(request, bill_id):
    """Generate PDF receipt for a specific bill using clean receipt template format"""
    from django.http import HttpResponse
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus.flowables import Flowable
    import io
    
    try:
        bill = get_object_or_404(WaterBill, id=bill_id)
    except WaterBill.DoesNotExist:
        return HttpResponse("Bill not found", status=404)
    
    # Create a file-like buffer to receive PDF data
    buffer = io.BytesIO()
    
    # Create the PDF object, using thermal receipt dimensions
    page_width = 2.8 * inch  # Thermal receipt width
    page_height = 11 * inch   # Long enough for content
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(page_width, page_height),
        rightMargin=0.15*inch,
        leftMargin=0.15*inch,
        topMargin=0.2*inch,
        bottomMargin=0.2*inch
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles matching the web receipt
    styles = getSampleStyleSheet()
    
    # Custom styles for thermal receipt
    company_style = ParagraphStyle(
        'CompanyName',
        parent=styles['Heading1'],
        fontSize=14,
        spaceAfter=3,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2c5aa0'),
        fontName='Helvetica-Bold'
    )
    
    title_style = ParagraphStyle(
        'ReceiptTitle',
        parent=styles['Normal'],
        fontSize=8,
        spaceAfter=2,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#666666')
    )
    
    section_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=10,
        spaceAfter=4,
        spaceBefore=8,
        textColor=colors.HexColor('#2c5aa0'),
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=8,
        spaceAfter=2
    )
    
    # Logo placeholder (simple circle with DW)
    class LogoFlowable(Flowable):
        def __init__(self, width=50, height=50):
            Flowable.__init__(self)
            self.width = width
            self.height = height
        
        def draw(self):
            # Draw circular logo with DW text
            self.canv.setFillColor(colors.HexColor('#2c5aa0'))
            self.canv.circle(self.width/2, self.height/2, self.width/2, fill=1)
            self.canv.setFillColor(colors.white)
            self.canv.setFont('Helvetica-Bold', 16)
            self.canv.drawCentredText(self.width/2, self.height/2-5, 'DW')
    
    # Add logo
    elements.append(Spacer(1, 5))
    logo = LogoFlowable()
    elements.append(logo)
    elements.append(Spacer(1, 8))
    
    # Add company header
    elements.append(Paragraph("DENKAM WATERS", company_style))
    elements.append(Paragraph("Kahawa Wendani Estate, Kiambu County", title_style))
    elements.append(Paragraph("Phone: +254 700 000 000 | Email: info@denkamwaters.co.ke", title_style))
    elements.append(Paragraph("<b>WATER BILL RECEIPT</b>", title_style))
    
    # Add separator line
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("_" * 40, ParagraphStyle('Separator', parent=normal_style, alignment=TA_CENTER)))
    elements.append(Spacer(1, 8))
    
    # Bill Information Section
    elements.append(Paragraph("Bill Information", section_style))
    
    bill_info = [
        ["Bill ID:", f"#{bill.id}"],
        ["Bill Date:", bill.created_on.strftime("%b %d, %Y")],
        ["Due Date:", bill.duedate.strftime("%b %d, %Y") if bill.duedate else "N/A"],
        ["Status:", bill.status],
    ]
    
    for label, value in bill_info:
        elements.append(Paragraph(f"<b>{label}</b> {value}", normal_style))
    
    elements.append(Spacer(1, 8))
    
    # Customer Information Section
    elements.append(Paragraph("Customer Information", section_style))
    
    customer_info = [
        ["Name:", str(bill.name)],
        ["Client ID:", str(bill.name.id)],
        ["Phone:", bill.name.phone or "N/A"],
        ["Status:", bill.name.status or "Connected"],
    ]
    
    for label, value in customer_info:
        elements.append(Paragraph(f"<b>{label}</b> {value}", normal_style))
    
    elements.append(Spacer(1, 8))
    
    # Bill Summary Section
    elements.append(Paragraph("Bill Summary", section_style))
    elements.append(Paragraph(f"<b>Total Bill Amount:</b> KSh {bill.payable():.2f}", normal_style))
    elements.append(Paragraph(f"<b>Amount Paid:</b> KSh {bill.total_paid:.2f}", normal_style))
    elements.append(Paragraph(f"<b>Outstanding Balance:</b> KSh {bill.balance_due:.2f}", normal_style))
    
    # Status indicator
    if bill.status == 'Paid':
        elements.append(Paragraph("✓ Fully Paid", ParagraphStyle('StatusPaid', parent=normal_style, 
                                textColor=colors.green, alignment=TA_CENTER, fontName='Helvetica-Bold')))
    elif bill.status == 'Partially Paid':
        elements.append(Paragraph("Partial payment received", ParagraphStyle('StatusPartial', parent=normal_style, 
                                textColor=colors.orange, alignment=TA_CENTER, fontName='Helvetica-Bold')))
    
    elements.append(Spacer(1, 8))
    
    # Payment Transactions Section
    if bill.status in ['Paid', 'Partially Paid']:
        elements.append(Paragraph("Payment Transactions", section_style))
        
        # Get payment details
        cash_payments = bill.cash_payments.all()
        mpesa_payments = bill.mpesa_payments.filter(result_code=0)
        
        if cash_payments.exists() or mpesa_payments.exists():
            # Create payment table
            payment_data = [["Date", "Method", "Reference", "Amount"]]
            
            for payment in cash_payments:
                payment_data.append([
                    payment.payment_date.strftime("%b %d"),
                    "Cash",
                    payment.reference_id[:8] + "...",  # Truncate for space
                    f"{payment.amount:.2f}"
                ])
            
            for payment in mpesa_payments:
                payment_data.append([
                    payment.created_at.strftime("%b %d"),
                    "M-Pesa",
                    payment.transaction_id[:8] + "...",  # Truncate for space
                    f"{payment.amount:.2f}"
                ])
            
            payment_table = Table(payment_data, colWidths=[0.5*inch, 0.5*inch, 0.6*inch, 0.5*inch])
            payment_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#ddd')),
            ]))
            
            elements.append(payment_table)
        else:
            elements.append(Paragraph("No payments recorded for this bill.", 
                                    ParagraphStyle('NoPayments', parent=normal_style, 
                                                 alignment=TA_CENTER, fontStyle='italic')))
        
        elements.append(Spacer(1, 8))
    
    # Total Section
    elements.append(Paragraph("_" * 40, ParagraphStyle('Separator', parent=normal_style, alignment=TA_CENTER)))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph(f"TOTAL: KSh {bill.payable():.2f}", 
                            ParagraphStyle('Total', parent=company_style, fontSize=12)))
    
    if bill.balance_due > 0:
        elements.append(Paragraph(f"Balance Due: KSh {bill.balance_due:.2f}", 
                                ParagraphStyle('BalanceDue', parent=normal_style, 
                                             textColor=colors.red, alignment=TA_CENTER, fontName='Helvetica-Bold')))
    
    elements.append(Spacer(1, 12))
    
    # Footer
    elements.append(Paragraph("Thank you for your payment!", 
                            ParagraphStyle('Footer', parent=normal_style, alignment=TA_CENTER)))
    elements.append(Paragraph(f"Generated on: {timezone.now().strftime('%b %d, %Y at %I:%M %p')}", 
                            ParagraphStyle('Generated', parent=normal_style, 
                                         alignment=TA_CENTER, fontSize=6, textColor=colors.HexColor('#666666'))))
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_{str(bill.name).replace(" ", "_")}_bill_{bill.id}.pdf"'
    response.write(pdf)
    
    return response


@login_required
@admin_required
def bulk_download_receipts(request):
    """Download multiple receipts as a single PDF"""
    if request.method == 'POST':
        bill_ids = request.POST.getlist('bill_ids')
        
        if not bill_ids:
            sweetify.error(request, 'No bills selected for download.')
            return redirect('history_bills')
        
        from django.http import HttpResponse
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.units import inch
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.platypus.flowables import Flowable
        import io
        
        # Get all selected bills
        bills = WaterBill.objects.filter(id__in=bill_ids)
        
        if not bills.exists():
            sweetify.error(request, 'Selected bills not found.')
            return redirect('history_bills')
        
        # Create a file-like buffer to receive PDF data
        buffer = io.BytesIO()
        
        # Create the PDF object, using thermal receipt dimensions
        page_width = 2.8 * inch  # Thermal receipt width
        page_height = 11 * inch   # Long enough for content
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=(page_width, page_height),
            rightMargin=0.15*inch,
            leftMargin=0.15*inch,
            topMargin=0.2*inch,
            bottomMargin=0.2*inch
        )
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Define styles matching the web receipt
        styles = getSampleStyleSheet()
        
        # Custom styles for thermal receipt
        company_style = ParagraphStyle(
            'CompanyName',
            parent=styles['Heading1'],
            fontSize=14,
            spaceAfter=3,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2c5aa0'),
            fontName='Helvetica-Bold'
        )
        
        title_style = ParagraphStyle(
            'ReceiptTitle',
            parent=styles['Normal'],
            fontSize=8,
            spaceAfter=2,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#666666')
        )
        
        section_style = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontSize=10,
            spaceAfter=4,
            spaceBefore=8,
            textColor=colors.HexColor('#2c5aa0'),
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=8,
            spaceAfter=2
        )
        
        # Logo placeholder (simple circle with DW)
        class LogoFlowable(Flowable):
            def __init__(self, width=50, height=50):
                Flowable.__init__(self)
                self.width = width
                self.height = height
            
            def draw(self):
                # Draw circular logo with DW text
                self.canv.setFillColor(colors.HexColor('#2c5aa0'))
                self.canv.circle(self.width/2, self.height/2, self.width/2, fill=1)
                self.canv.setFillColor(colors.white)
                self.canv.setFont('Helvetica-Bold', 16)
                self.canv.drawCentredText(self.width/2, self.height/2-5, 'DW')
        
        # Generate receipt for each bill
        for i, bill in enumerate(bills):
            # Add logo
            elements.append(Spacer(1, 5))
            logo = LogoFlowable()
            elements.append(logo)
            elements.append(Spacer(1, 8))
            
            # Add company header
            elements.append(Paragraph("DENKAM WATERS", company_style))
            elements.append(Paragraph("Kahawa Wendani Estate, Kiambu County", title_style))
            elements.append(Paragraph("Phone: +254 700 000 000 | Email: info@denkamwaters.co.ke", title_style))
            elements.append(Paragraph("<b>WATER BILL RECEIPT</b>", title_style))
            
            # Add separator line
            elements.append(Spacer(1, 8))
            elements.append(Paragraph("_" * 40, ParagraphStyle('Separator', parent=normal_style, alignment=TA_CENTER)))
            elements.append(Spacer(1, 8))
            
            # Bill Information Section
            elements.append(Paragraph("Bill Information", section_style))
            elements.append(Paragraph(f"<b>Bill ID:</b> #{bill.id}", normal_style))
            elements.append(Paragraph(f"<b>Bill Date:</b> {bill.created_on.strftime('%b %d, %Y')}", normal_style))
            elements.append(Paragraph(f"<b>Due Date:</b> {bill.duedate.strftime('%b %d, %Y') if bill.duedate else 'N/A'}", normal_style))
            elements.append(Paragraph(f"<b>Status:</b> {bill.status}", normal_style))
            elements.append(Spacer(1, 8))
            
            # Customer Information Section
            elements.append(Paragraph("Customer Information", section_style))
            elements.append(Paragraph(f"<b>Name:</b> {str(bill.name)}", normal_style))
            elements.append(Paragraph(f"<b>Client ID:</b> {str(bill.name.id)}", normal_style))
            elements.append(Paragraph(f"<b>Phone:</b> {bill.name.phone or 'N/A'}", normal_style))
            elements.append(Spacer(1, 8))
            
            # Bill Summary Section
            elements.append(Paragraph("Bill Summary", section_style))
            elements.append(Paragraph(f"<b>Total Bill Amount:</b> KSh {bill.payable():.2f}", normal_style))
            elements.append(Paragraph(f"<b>Amount Paid:</b> KSh {bill.total_paid:.2f}", normal_style))
            elements.append(Paragraph(f"<b>Outstanding Balance:</b> KSh {bill.balance_due:.2f}", normal_style))
            
            # Status indicator
            if bill.status == 'Paid':
                elements.append(Paragraph("✓ Fully Paid", ParagraphStyle('StatusPaid', parent=normal_style, 
                                        textColor=colors.green, alignment=TA_CENTER, fontName='Helvetica-Bold')))
            elif bill.status == 'Partially Paid':
                elements.append(Paragraph("Partial payment received", ParagraphStyle('StatusPartial', parent=normal_style, 
                                        textColor=colors.orange, alignment=TA_CENTER, fontName='Helvetica-Bold')))
            
            elements.append(Spacer(1, 8))
            
            # Total Section
            elements.append(Paragraph("_" * 40, ParagraphStyle('Separator', parent=normal_style, alignment=TA_CENTER)))
            elements.append(Spacer(1, 5))
            elements.append(Paragraph(f"TOTAL: KSh {bill.payable():.2f}", 
                                    ParagraphStyle('Total', parent=company_style, fontSize=12)))
            
            if bill.balance_due > 0:
                elements.append(Paragraph(f"Balance Due: KSh {bill.balance_due:.2f}", 
                                        ParagraphStyle('BalanceDue', parent=normal_style, 
                                                     textColor=colors.red, alignment=TA_CENTER, fontName='Helvetica-Bold')))
            
            elements.append(Spacer(1, 12))
            
            # Footer
            elements.append(Paragraph("Thank you for your payment!", 
                                    ParagraphStyle('Footer', parent=normal_style, alignment=TA_CENTER)))
            elements.append(Paragraph(f"Generated on: {timezone.now().strftime('%b %d, %Y at %I:%M %p')}", 
                                    ParagraphStyle('Generated', parent=normal_style, 
                                                 alignment=TA_CENTER, fontSize=6, textColor=colors.HexColor('#666666'))))
            
            # Add page break between receipts (except for the last one)
            if i < len(bills) - 1:
                elements.append(PageBreak())
        
        # Build PDF
        doc.build(elements)
        
        # Get the value of the BytesIO buffer and write it to the response
        pdf = buffer.getvalue()
        buffer.close()
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="bulk_receipts_{len(bills)}_bills_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
        response.write(pdf)
        
        return response
    
    return redirect('history_bills')


@login_required
@customer_or_admin_required
def ongoing_bills(request):
    """View and manage ongoing/unpaid bills"""
    from decimal import Decimal
    
    if request.user.role == Account.Role.ADMIN:
        # Admin sees all ongoing bills
        ongoingbills = WaterBill.objects.filter(
            status__in=['Pending', 'Partially Paid']
        ).order_by('-created_on')
    else:
        # Customer sees only their bills
        ongoingbills = WaterBill.objects.filter(
            name__name=request.user,
            status__in=['Pending', 'Partially Paid']
        ).order_by('-created_on')
    
    # Calculate totals for dashboard
    total_amount_due = sum(Decimal(str(bill.payable())) for bill in ongoingbills)
    overdue_count = 0
    
    from django.utils import timezone
    today = timezone.now().date()
    
    for bill in ongoingbills:
        if bill.duedate and bill.duedate < today:
            overdue_count += 1
    
    context = {
        'title': 'Manage Unpaid Bills',
        'ongoingbills': ongoingbills,
        'total_bills': ongoingbills.count(),
        'total_amount_due': total_amount_due,
        'overdue_count': overdue_count,
    }
    
    return render(request, 'main/billsongoing.html', context)

