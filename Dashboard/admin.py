# admin.py
from django.contrib import admin
from .models import Booking

from django.contrib import admin
from django.utils.html import format_html
from .models import GalleryItem


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("name", "service", "date", "time", "status", "email")
    list_filter = ("status", "service", "date")
    search_fields = ("name", "email")
    list_editable = ("status",)

@admin.register(GalleryItem)
class GalleryItemAdmin(admin.ModelAdmin):
    list_display = ("preview", "name", "created")
    search_fields = ("name", "description")

    def preview(self, obj):
        return format_html('<img src="{}" style="height:50px;border-radius:6px">', obj.image.url) if obj.image else ""