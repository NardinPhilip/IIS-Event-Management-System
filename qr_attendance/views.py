# qr_attendance/views.py
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction
import pandas as pd
import qrcode
from PIL import Image
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader  # Import ImageReader
from arabic_reshaper import reshape
from bidi.algorithm import get_display
from .models import Attendee, Attendance
import uuid
import os
import logging
from django.conf import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Register Arabic fonts with error handling
try:
    font_dir = os.path.join(settings.STATICFILES_DIRS[0], 'fonts')
    font_path = os.path.join(font_dir, 'Amiri-Regular.ttf')
    bold_font_path = os.path.join(font_dir, 'Amiri-Bold.ttf')
    if not os.path.exists(font_path) or not os.path.exists(bold_font_path):
        raise FileNotFoundError(f"Font files not found in {font_dir}")
    pdfmetrics.registerFont(TTFont('Amiri', font_path))
    pdfmetrics.registerFont(TTFont('Amiri-Bold', bold_font_path))
    logger.info("Fonts registered successfully")
except Exception as e:
    logger.error(f"Font registration failed: {str(e)}")
    raise

def upload_excel(request):
    if request.method == 'POST':
        excel_file = request.FILES['excel_file']
        try:
            df = pd.read_excel(excel_file)
            attendees_to_create = []
            existing_attendees = set(
                Attendee.objects.values_list('name', 'job_title', flat=False)
            )
            duplicates = []
            for _, row in df.iterrows():
                name = row['Name']
                job_title = row['Job Title']
                key = (name, job_title)
                if key not in existing_attendees:
                    attendees_to_create.append(
                        Attendee(name=name, job_title=job_title, qr_code=str(uuid.uuid4()))
                    )
                else:
                    duplicates.append(f"{name} ({job_title})")
            if attendees_to_create:
                with transaction.atomic():
                    Attendee.objects.bulk_create(attendees_to_create, batch_size=500)
            if duplicates:
                error_msg = "Skipped duplicates: " + ", ".join(duplicates)
                return render(request, 'qr_attendance/upload.html', {'error': error_msg})
            return redirect('attendee_list')
        except Exception as e:
            logger.error(f"Upload error: {str(e)}")
            return render(request, 'qr_attendance/upload.html', {'error': str(e)})
    return render(request, 'qr_attendance/upload.html')

def generate_qr_stickers(request):
    try:
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        attendees = Attendee.objects.all()
        if not attendees.exists():
            return HttpResponse("No attendees found", status=404)
        
        qr_size = 180 * mm
        qr_configs = []
        for attendee in attendees:
            qr = qrcode.QRCode(
                version=2,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=18,
                border=4
            )
            qr.add_data(attendee.qr_code)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_buffer = BytesIO()
            qr_img.save(qr_buffer, format="PNG")
            qr_buffer.seek(0)  # Reset buffer position
            qr_configs.append((attendee, qr_buffer))
        
        top_margin = 20 * mm
        welcome_font_size = 60
        name_font_size = 60
        for attendee, qr_buffer in qr_configs:
            page_center_x = A4[0] / 2
            welcome_y_start = A4[1] - top_margin - (welcome_font_size * 1.5 / 2.83465) * 2
            qr_y = (A4[1] - qr_size) / 2 - 5 * mm
            
            welcome_text_part1 = "Welcome to"
            welcome_text_part2 = "ACOC25 Iftar"
            reshaped_part1 = reshape(welcome_text_part1)
            bidi_part1 = get_display(reshaped_part1)
            reshaped_part2 = reshape(welcome_text_part2)
            bidi_part2 = get_display(reshaped_part2)
            
            p.setFont("Amiri-Bold", welcome_font_size)
            line_height = welcome_font_size * 2.3 / 2.83465
            text_y = welcome_y_start
            p.drawCentredString(page_center_x, text_y, bidi_part1)
            text_y -= line_height
            p.drawCentredString(page_center_x, text_y, bidi_part2)
            
            # Use ImageReader to wrap the BytesIO object
            qr_image = ImageReader(qr_buffer)
            p.drawImage(qr_image, (A4[0] - qr_size) / 2, qr_y, width=qr_size, height=qr_size, mask='auto')
            
            name_text = get_display(reshape(attendee.name))
            name_y = qr_y - 30 * mm
            p.setFont("Amiri-Bold", name_font_size)
            p.drawCentredString(page_center_x, name_y, name_text)
            
            p.showPage()
            qr_buffer.close()
        
        p.save()
        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename='qr_stickers.pdf')
    except Exception as e:
        logger.error(f"QR generation failed: {str(e)}")
        return HttpResponse(f"Error generating QR stickers: {str(e)}", status=500)

def attendee_list(request):
    attendees = Attendee.objects.all()[:25]
    total_attendees = Attendee.objects.count()
    return render(request, 'qr_attendance/attendee_list.html', {
        'attendees': attendees,
        'total_attendees': total_attendees
    })

@require_http_methods(["GET"])
def get_attendees_paginated(request):
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 25))
        start = (page - 1) * per_page
        end = start + per_page
        attendees = Attendee.objects.all()[start:end]
        total_attendees = Attendee.objects.count()
        data = [{
            'name': attendee.name,
            'job_title': attendee.job_title,
            'qr_code': attendee.qr_code
        } for attendee in attendees]
        return JsonResponse({
            'status': 'success',
            'attendees': data,
            'total': total_attendees,
            'page': page,
            'per_page': per_page
        })
    except Exception as e:
        logger.error(f"Pagination error: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_http_methods(["GET", "POST"])
@csrf_exempt
def scan_qr(request, code):
    try:
        attendee = Attendee.objects.get(qr_code=code)
        if request.method == "GET":
            return JsonResponse({"status": "success", "name": attendee.name, "job_title": attendee.job_title})
        elif request.method == "POST":
            if Attendance.objects.filter(attendee=attendee).exists():
                return JsonResponse({"status": "exists", "message": "Attendance already recorded."})
            attendance = Attendance.objects.create(attendee=attendee)
            return JsonResponse({
                "status": "success",
                "message": "Attendance recorded successfully.",
                "timestamp": attendance.timestamp.strftime("%Y-%m-%d %H:%M")
            })
    except Attendee.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Invalid QR code."}, status=404)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

def attendance_list(request):
    attendances = Attendance.objects.all().order_by('-timestamp')[:25]
    return render(request, 'qr_attendance/attendance_list.html', {'attendances': attendances})

def scan_page(request):
    attendances = Attendance.objects.all().order_by('-timestamp')[:25]
    return render(request, 'qr_attendance/scan.html', {'attendances': attendances})

def flush_attendees(request):
    if request.method == 'POST':
        Attendee.objects.all().delete()
        return redirect('attendee_list')
    return redirect('attendee_list')

def flush_attendance(request):
    if request.method == 'POST':
        Attendance.objects.all().delete()
        return redirect('attendance_list')
    return redirect('attendance_list')