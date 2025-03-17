# qr_attendance/models.py
from django.db import models

class Attendee(models.Model):
    name = models.CharField(max_length=100, db_index=True)  # Indexed for faster lookups
    job_title = models.CharField(max_length=100, db_index=True)  # Indexed for faster lookups
    qr_code = models.CharField(max_length=100, unique=True, null=True, db_index=True)  # Indexed for scan lookups
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['name', 'job_title']),  # Composite index for duplicate checks
        ]

    def __str__(self):
        return f"{self.name} ({self.job_title})"

class Attendance(models.Model):
    attendee = models.ForeignKey(Attendee, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)  # Indexed for ordering
    status = models.CharField(max_length=20, default='Present')

    class Meta:
        indexes = [
            models.Index(fields=['attendee', 'timestamp']),  # For filtering and ordering
        ]

    def __str__(self):
        return f"{self.attendee.name} - {self.timestamp}"