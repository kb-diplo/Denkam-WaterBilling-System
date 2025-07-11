from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import requests
import json
import base64
import logging
from datetime import datetime
from django.conf import settings
from .models import MpesaPayment
from main.models import WaterBill

logger = logging.getLogger(__name__)

def get_mpesa_access_token():
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET
    api_url = f'{settings.MPESA_API_URL}/oauth/v1/generate?grant_type=client_credentials'

    if not consumer_key or not consumer_secret:
        logger.error("MPESA_CONSUMER_KEY or MPESA_CONSUMER_SECRET not configured in settings.")
        return None

    try:
        response = requests.get(api_url, auth=(consumer_key, consumer_secret))
        
        if response.status_code == 200:
            logger.info("Successfully obtained M-Pesa access token.")
            return response.json()['access_token']
        else:
            logger.error(f"Failed to get M-Pesa access token. Status: {response.status_code}, Response: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while requesting M-Pesa access token: {e}")
        return None

@csrf_exempt
def initiate_payment(request, bill_id):
    bill = get_object_or_404(WaterBill, id=bill_id)
    
    if request.method == 'POST':
        phone_number_str = request.POST.get('phone_number')
        amount_str = request.POST.get('amount')
        
        if not phone_number_str:
            return JsonResponse({'error': 'Phone number is required.'}, status=400)
        
        if phone_number_str.startswith('+254'):
            phone_number = phone_number_str[1:]
        elif phone_number_str.startswith('07'):
            phone_number = '254' + phone_number_str[1:]
        elif phone_number_str.startswith('01'):
            phone_number = '254' + phone_number_str[1:]
        elif phone_number_str.startswith('254'):
            phone_number = phone_number_str
        else:
            return JsonResponse({'error': 'Invalid phone number format. Use 07xxxxxxxx, 01xxxxxxxx or 254xxxxxxxx.'}, status=400)

        try:
            amount = int(float(amount_str))
            if amount < 1:
                return JsonResponse({'error': 'Invalid amount.'}, status=400)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid amount provided.'}, status=400)

        access_token = get_mpesa_access_token()
        if not access_token:
            logger.error("Could not get M-Pesa access token.")
            return JsonResponse({'error': 'Could not get access token.'}, status=500)

        api_url = f'{settings.MPESA_API_URL}/mpesa/stkpush/v1/processrequest'
        headers = {'Authorization': f'Bearer {access_token}'}

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(f'{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}'.encode()).decode('utf-8')

        payload = {
            'BusinessShortCode': settings.MPESA_SHORTCODE,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': 'CustomerPayBillOnline',
            'Amount': amount,
            'PartyA': phone_number,
            'PartyB': settings.MPESA_SHORTCODE,
            'PhoneNumber': phone_number,
            'CallBackURL': settings.MPESA_CALLBACK_URL,
            'AccountReference': f'BILL-{bill.id}',
            'TransactionDesc': f'Payment for Water Bill {bill.id}'
        }

        logger.info(f"Initiating M-Pesa payment with payload: {payload}")
        
        try:
            response = requests.post(api_url, json=payload, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            logger.info(f"M-Pesa push response: {response_data}")
            return JsonResponse(response_data)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling M-Pesa API: {e}")
            return JsonResponse({'error': f'Failed to communicate with M-Pesa API: {str(e)}'}, status=500)

    return render(request, 'mpesa/initiate_payment.html', {'bill': bill})

@csrf_exempt
def mpesa_callback(request):
    data = json.loads(request.body)
    
    # Process the callback data
    # Check if the transaction was successful and update the database
    # This is a simplified example. You should add more robust error handling and security checks.
    
    result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode')

    if result_code == 0:
        # Successful transaction
        callback_metadata = data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', [])
        
        amount = next((item['Value'] for item in callback_metadata if item['Name'] == 'Amount'), None)
        receipt_number = next((item['Value'] for item in callback_metadata if item['Name'] == 'MpesaReceiptNumber'), None)
        phone_number = next((item['Value'] for item in callback_metadata if item['Name'] == 'PhoneNumber'), None)
        account_reference = data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID') # Or use AccountReference from initiate_payment

        # Find the bill and update its status
        # You might need a more robust way to link the callback to the initial payment request
        try:
            # This is a simplified lookup. In a real application, you'd use the CheckoutRequestID
            # stored during initiation to find the correct MpesaPayment record.
            bill_id = int(account_reference.split('-')[1]) # Assuming AccountReference is 'BILL-<id>'
            bill = WaterBill.objects.get(id=bill_id)
            bill.status = 'Paid'
            bill.save()

            # Create a MpesaPayment record
            MpesaPayment.objects.create(
                bill=bill,
                phone_number=phone_number,
                amount=amount,
                transaction_id=receipt_number,
                is_successful=True
            )
        except (WaterBill.DoesNotExist, IndexError, ValueError):
            # Handle cases where the bill is not found or the reference is malformed
            pass

    return HttpResponse(status=200)
