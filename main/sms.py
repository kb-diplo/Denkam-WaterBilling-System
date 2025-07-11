import os
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv() # take environment variables from .env.

# Your Account SID and Auth Token from your .env file
SID = os.getenv('TWILIO_SID')
Auth_Token = os.getenv('TWILIO_AUTH_TOKEN')
sender = os.getenv('TWILIO_SENDER_PHONE')

# This is a placeholder and should be dynamic in a real application
receiver = '639105685214' 

if SID and Auth_Token and sender:
    try:
        cl = Client(SID, Auth_Token)
        cl.messages.create(body='Test', from_=sender, to=receiver)
        print("SMS sent successfully!")
    except Exception as e:
        print(f"Error sending SMS: {e}")
else:
    print("Twilio credentials not found in environment variables.")