import uuid

from django.conf import settings
from django.db import models

import os
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image, ImageOps


class Booking(models.Model):
    SERVICES = [
        ("braids", "Knotless Braids — KES 3,500"),
        ("manicure", "Manicure — KES 1,800"),
        ("haircare", "Natural Haircare — KES 2,500"),
    ]
    PRICES = {"braids": 3500, "manicure": 1800, "haircare": 2500}
    STATUS = [("pending", "Pending"), ("confirmed", "Confirmed"), ("cancelled", "Cancelled")]
    PAYMENT = [
        ("unpaid", "Unpaid"),
        ("pending", "Awaiting payment"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    # booking details
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    service = models.CharField(max_length=20, choices=SERVICES)
    date = models.DateField()
    time = models.TimeField()
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    # payment details
    amount = models.PositiveIntegerField(default=0)
    payment_status = models.CharField(max_length=10, choices=PAYMENT, default="unpaid")
    mpesa_phone = models.CharField(max_length=15, blank=True)
    merchant_request_id = models.CharField(max_length=60, blank=True)
    checkout_request_id = models.CharField(max_length=60, blank=True, db_index=True)
    mpesa_receipt = models.CharField(max_length=30, blank=True)
    payment_note = models.CharField(max_length=200, blank=True)
    payment_requested_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["date", "time"]

    def save(self, *args, **kwargs):
        if not self.amount:   # the price is always set on the server, never by the browser
            percent = getattr(settings, "BOOKING_DEPOSIT_PERCENT", 100)
            self.amount = max(1, self.PRICES.get(self.service, 0) * percent // 100)
        super().save(*args, **kwargs)

    @property
    def service_name(self):
        return self.get_service_display().split(" — ")[0]

    def __str__(self):
        return f"{self.name} – {self.service_name} on {self.date} {self.time:%H:%M}"

class GalleryItem(models.Model):
    name = models.CharField("Hairstyle name", max_length=100)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="gallery/")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def save(self, *args, **kwargs):
        # Resize only when a new file was just uploaded
        if self.image and not getattr(self.image, "_committed", True):
            img = ImageOps.exif_transpose(Image.open(self.image)).convert("RGB")
            img.thumbnail((1400, 1400))
            buf = BytesIO()
            img.save(buf, "JPEG", quality=82, optimize=True)
            base = os.path.splitext(os.path.basename(self.image.name))[0]
            self.image.save(base + ".jpg", ContentFile(buf.getvalue()), save=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name