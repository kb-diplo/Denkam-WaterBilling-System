from django.test import TestCase
from django.conf import settings

class MpesaIntegrationTest(TestCase):
    def test_mpesa_environment_variables_loaded(self):
        """Test that M-Pesa environment variables are loaded correctly"""
        self.assertIsNotNone(settings.MPESA_CONSUMER_KEY)
        self.assertIsNotNone(settings.MPESA_CONSUMER_SECRET)
        self.assertIsNotNone(settings.MPESA_SHORTCODE)
        self.assertIsNotNone(settings.MPESA_PASSKEY)
        
    def test_mpesa_environment_variables_not_empty(self):
        """Test that M-Pesa environment variables are not empty strings"""
        self.assertNotEqual(settings.MPESA_CONSUMER_KEY, '')
        self.assertNotEqual(settings.MPESA_CONSUMER_SECRET, '')
        self.assertNotEqual(settings.MPESA_SHORTCODE, '')
        self.assertNotEqual(settings.MPESA_PASSKEY, '')
