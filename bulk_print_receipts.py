from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from main.decorators import admin_required
from main.models import WaterBill
import sweetify
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from io import BytesIO
import datetime

@login_required
@admin_required
def bulk_print_receipts(request):
    """Generate bulk thermal receipts for multiple bills"""
    
    # Get selected bill IDs from POST data
    if request.method == 'POST':
        selected_bills = request.POST.getlist('selected_bills')
        if not selected_bills:
            sweetify.error(request, 'Please select at least one bill to print.')
            return redirect('ongoing_bills')
        
        bills = WaterBill.objects.filter(id__in=selected_bills)
    else:
        # Default to all unpaid bills
        bills = WaterBill.objects.filter(status__in=['Pending', 'Partially Paid'])
    
    if not bills.exists():
        sweetify.error(request, 'No bills found for printing.')
        return redirect('ongoing_bills')
    
    # Create the PDF object for bulk receipts
    buffer = BytesIO()
    # Thermal receipt size (2.8 inches wide for thermal printers)
    receipt_width = 2.8 * inch
    receipt_height = 11 * inch
    doc = SimpleDocTemplate(buffer, pagesize=(receipt_width, receipt_height), 
                           rightMargin=0.1*inch, leftMargin=0.1*inch, 
                           topMargin=0.1*inch, bottomMargin=0.1*inch)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Company style for thermal receipts
    company_style = ParagraphStyle(
        'CompanyName',
        parent=styles['Normal'],
        fontSize=9,
        alignment=1,  # Center
        fontName='Helvetica-Bold',
        spaceAfter=2
    )
    
    receipt_style = ParagraphStyle(
        'ReceiptHeader',
        parent=styles['Normal'],
        fontSize=7,
        alignment=1,  # Center
        fontName='Helvetica',
        spaceAfter=2
    )
    
    # Generate receipts for each bill
    for i, bill in enumerate(bills):
        # Add company header
        elements.append(Paragraph("DENKAM WATERS", company_style))
        elements.append(Paragraph(f"BILL RECEIPT #{bill.id}", receipt_style))
        elements.append(Paragraph("=" * 30, receipt_style))
        elements.append(Spacer(1, 5))
        
        # Bill information
        bill_data = [
            ['Bill ID:', f"#{bill.id}"],
            ['Date:', bill.created_on.strftime('%b %d, %Y')],
            ['Customer:', str(bill.name)],
            ['Due Date:', bill.duedate.strftime('%b %d, %Y') if bill.duedate else 'N/A'],
            ['Status:', bill.status],
        ]
        
        bill_table = Table(bill_data, colWidths=[0.8*inch, 1.8*inch])
        bill_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
        ]))
        
        elements.append(bill_table)
        elements.append(Spacer(1, 5))
        
        # Charges
        elements.append(Paragraph("=" * 30, receipt_style))
        elements.append(Paragraph("CHARGES", receipt_style))
        elements.append(Paragraph("=" * 30, receipt_style))
        
        charges_data = [
            ['Water Usage', f'{bill.payable():.2f}'],
        ]
        
        charges_table = Table(charges_data, colWidths=[1.8*inch, 0.8*inch])
        charges_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ]))
        
        elements.append(charges_table)
        elements.append(Paragraph("=" * 30, receipt_style))
        elements.append(Paragraph(f"TOTAL: KSh {bill.payable():.2f}", receipt_style))
        elements.append(Paragraph("=" * 30, receipt_style))
        
        # Payment status
        if bill.status == 'Paid':
            elements.append(Paragraph("*** PAID ***", receipt_style))
        elif bill.status == 'Partially Paid':
            elements.append(Paragraph(f"BALANCE: KSh {bill.balance_due:.2f}", receipt_style))
        else:
            elements.append(Paragraph("*** PENDING PAYMENT ***", receipt_style))
        
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("Thank you for choosing Denkam Waters!", receipt_style))
        
        # Add page break between receipts (except for the last one)
        if i < len(bills) - 1:
            elements.append(PageBreak())
    
    # Build PDF
    doc.build(elements)
    
    # Return PDF response
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="bulk_receipts_{len(bills)}_bills.pdf"'
    
    return response
