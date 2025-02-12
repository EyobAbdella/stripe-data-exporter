from django.db import models
from django.conf import settings


class Export(models.Model):
    ALL_PAYMENTS = "ALL_PAYMENTS"
    ALL_TRANSACTIONS = "ALL_TRANSACTIONS"
    EXPORT_CHOICES = [
        (ALL_PAYMENTS, "All_Payments"),
        (ALL_TRANSACTIONS, "All_Transactions"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exports"
    )
    export_type = models.CharField(max_length=20, choices=EXPORT_CHOICES)
    file_name = models.CharField(max_length=100)
    date_range = models.CharField(max_length=100)
    columns = models.JSONField(default=list)
    sheet_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
