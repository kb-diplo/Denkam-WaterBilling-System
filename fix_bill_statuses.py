#!/usr/bin/env python
import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from main.models import WaterBill

def fix_all_bill_statuses():
    """Fix all bill statuses based on actual payment records"""
    print("Starting bill status validation and correction...")
    
    bills = WaterBill.objects.all()
    corrected_count = 0
    
    for bill in bills:
        old_status = bill.status
        
        # Update status based on payments
        bill.update_status_based_on_payments()
        bill.refresh_from_db()
        new_status = bill.status
        
        if old_status != new_status:
            corrected_count += 1
            print(f"Bill #{bill.id} ({bill.name.name}) status corrected: {old_status} -> {new_status}")
            print(f"  Total Paid: KSh {bill.total_paid:.2f}, Total Due: KSh {bill.payable():.2f}")
    
    print(f"\nTotal bills corrected: {corrected_count}")
    print("Bill status validation completed!")
    
    return corrected_count

if __name__ == "__main__":
    fix_all_bill_statuses()
