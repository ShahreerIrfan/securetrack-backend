from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

ALLOWED_ATTACHMENT_EXTENSIONS = [
    'pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'txt', 'log', 'csv', 'zip', 'docx',
]
MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_attachment_size(file):
    if file.size > MAX_ATTACHMENT_SIZE_BYTES:
        raise ValidationError('Attachment must be 10MB or smaller.')


class Report(models.Model):
    class Severity(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        CRITICAL = 'critical', 'Critical'

    class Status(models.TextChoices):
        NEW = 'new', 'New'
        IN_REVIEW = 'in_review', 'In Review'
        VERIFIED = 'verified', 'Verified'
        ASSIGNED = 'assigned', 'Assigned'
        RESOLVED = 'resolved', 'Resolved'
        CLOSED = 'closed', 'Closed'

    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'

    class Category(models.TextChoices):
        WEB_APPLICATION = 'web_application', 'Web Application'
        NETWORK = 'network', 'Network'
        PHYSICAL_SECURITY = 'physical_security', 'Physical Security'
        SOCIAL_ENGINEERING = 'social_engineering', 'Social Engineering'
        OTHER = 'other', 'Other'

    class VulnerabilityType(models.TextChoices):
        SQL_INJECTION = 'sql_injection', 'SQL Injection'
        XSS = 'xss', 'Cross-Site Scripting (XSS)'
        CSRF = 'csrf', 'Cross-Site Request Forgery (CSRF)'
        BROKEN_AUTH = 'broken_authentication', 'Broken Authentication'
        DATA_EXPOSURE = 'data_exposure', 'Sensitive Data Exposure'
        MISCONFIGURATION = 'misconfiguration', 'Security Misconfiguration'
        INSECURE_API = 'insecure_api', 'Insecure API'
        MALWARE = 'malware', 'Malware Infection'
        RANSOMWARE = 'ransomware', 'Ransomware'
        PHISHING = 'phishing', 'Phishing Attack'
        DDOS = 'ddos', 'DDoS Attack'
        MITM = 'mitm', 'Man-in-the-Middle Attack'
        INSIDER_THREAT = 'insider_threat', 'Insider Threat'
        ZERO_DAY = 'zero_day', 'Zero-Day Exploit'
        OTHER = 'other', 'Other'

    title = models.CharField(max_length=255)
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.OTHER)
    vulnerability_type = models.CharField(
        max_length=30, choices=VulnerabilityType.choices, default=VulnerabilityType.OTHER,
    )
    due_date = models.DateField(null=True, blank=True)
    attachment = models.FileField(
        upload_to='report_attachments/%Y/%m/',
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(allowed_extensions=ALLOWED_ATTACHMENT_EXTENSIONS),
            validate_attachment_size,
        ],
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_created',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports_assigned',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Comment(models.Model):
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Comment by {self.author} on {self.report}'


class ActivityLog(models.Model):
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='activity_logs')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action = models.CharField(max_length=100)
    detail = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.action} on {self.report} by {self.actor}'
