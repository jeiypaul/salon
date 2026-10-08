import hmac
import json

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import mpesa
from .form import BookingForm
from .models import Booking
from django.contrib import messages
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .form import GalleryItemForm
from .models import GalleryItem


# ---------- public site ----------
def index(request):
    if request.method == "POST":
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save()
            messages.success(
                request,
                f"Booking successful! Thank you, {booking.name}. Your "
                f"{booking.service_name} appointment on {booking.date:%A, %d %B %Y} "
                f"at {booking.time:%I:%M %p} is saved. Complete payment below to secure your slot."
            )
            return redirect("payment", ref=booking.reference)
    else:
        form = BookingForm()
    return render(request, "index.html", {"form": form})


# ---------- payment ----------

def _apply_result(booking, code, desc, metadata=None):
    """Update a booking from an M-Pesa result (callback or query)."""
    if code == 0:
        items = {i["Name"]: i.get("Value") for i in (metadata or {}).get("Item", [])}
        booking.payment_status = "paid"
        booking.status = "confirmed"
        booking.payment_note = ""
        booking.paid_at = booking.paid_at or timezone.now()
        if items.get("MpesaReceiptNumber"):
            booking.mpesa_receipt = str(items["MpesaReceiptNumber"])
    elif booking.payment_status != "paid":
        booking.payment_status = "failed"
        booking.payment_note = desc or "The payment was not completed."
    booking.save()


def payment(request, ref):
    booking = get_object_or_404(Booking, reference=ref)

    if request.GET.get("retry") and booking.payment_status in ("pending", "failed"):
        booking.payment_status = "unpaid"
        booking.save(update_fields=["payment_status"])
        return redirect("payment", ref=booking.reference)

    error = ""
    if request.method == "POST" and booking.payment_status != "paid":
        phone = mpesa.normalize_phone(request.POST.get("phone"))
        if not phone:
            error = "Enter a valid Safaricom number, e.g. 0712 345 678."
        else:
            try:
                data = mpesa.stk_push(phone, booking.amount, f"GLOW{booking.pk}")
            except mpesa.MpesaError as e:
                error = str(e)
            else:
                booking.mpesa_phone = phone
                booking.merchant_request_id = data.get("MerchantRequestID", "")
                booking.checkout_request_id = data.get("CheckoutRequestID", "")
                booking.payment_status = "pending"
                booking.payment_note = ""
                booking.payment_requested_at = timezone.now()
                booking.save()
                return redirect("payment", ref=booking.reference)

    return render(request, "payment.html", {"booking": booking, "error": error})


@require_GET
def payment_status(request, ref):
    """Polled by the payment page every few seconds."""
    booking = get_object_or_404(Booking, reference=ref)

    # If the callback is slow or missed, ask Safaricom directly after 20 seconds.
    if (booking.payment_status == "pending" and booking.checkout_request_id
            and booking.payment_requested_at
            and (timezone.now() - booking.payment_requested_at).total_seconds() > 20):
        try:
            result = mpesa.stk_query(booking.checkout_request_id)
        except mpesa.MpesaError:
            result = {}
        if "ResultCode" in result:   # absent while the customer is still deciding
            _apply_result(booking, int(result["ResultCode"]), result.get("ResultDesc", ""))

    return JsonResponse({"status": booking.payment_status})


@csrf_exempt
@require_POST
def mpesa_callback(request, secret):
    """Safaricom posts the payment result here."""
    if not hmac.compare_digest(secret, settings.MPESA_CALLBACK_SECRET):
        raise Http404
    try:
        cb = json.loads(request.body)["Body"]["stkCallback"]
        code = int(cb["ResultCode"])
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid payload"})

    booking = Booking.objects.filter(checkout_request_id=cb.get("CheckoutRequestID")).first()
    if booking:
        _apply_result(booking, code, cb.get("ResultDesc", ""), cb.get("CallbackMetadata"))
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


# ---------- staff dashboard ----------

@staff_member_required(login_url="dashboard_login")
def bookings_list(request):
    qs = Booking.objects.all()

    status = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()

    if status in dict(Booking.STATUS):
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q))

    counts = {s: Booking.objects.filter(status=s).count() for s, _ in Booking.STATUS}
    counts["all"] = sum(counts.values())

    return render(request, "dashboard/bookings.html", {
        "bookings": qs,
        "counts": counts,
        "status": status,
        "q": q,
        "statuses": Booking.STATUS,
    })


@staff_member_required(login_url="dashboard_login")
@require_POST
def update_status(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    new_status = request.POST.get("status")
    if new_status in dict(Booking.STATUS):
        booking.status = new_status
        booking.save(update_fields=["status"])
    return redirect("dashboard")

staff_only = user_passes_test(lambda u: u.is_staff, login_url="dashboard_login")


def gallery(request):
    form = GalleryItemForm()

    if request.method == "POST":
        if not request.user.is_staff:
            return redirect("dashboard_login")
        form = GalleryItemForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Photo added to the gallery.")
            return redirect("gallery")

    return render(request, "gallery.html", {
        "items": GalleryItem.objects.all(),
        "form": form,
    })


@staff_only
@require_POST
def gallery_delete(request, pk):
    get_object_or_404(GalleryItem, pk=pk).delete()
    messages.success(request, "Photo removed.")
    return redirect("gallery")

def services(request):
    services = [
        {"slug": "hair", "name": "Hair", "icon": "💇‍♀️", "image": "images/hair.jpg",
         "price_label": "Braids", "price": 1500,
         "items": ["Braiding (Knotless, Box Braids, Cornrows, Fulani)", "Weaving & Extensions",
                   "Natural Hair Care / Treatment", "Blowdry & Styling",
                   "Dreadlocks (Installation & Retouch)", "Hair Coloring & Highlights",
                   "Haircuts (Women & Kids)"]},
        {"slug": "barber", "name": "Barber", "icon": "💈", "image": "images/barber.jpg",
         "price_label": "Cuts", "price": 300,
         "items": ["Haircuts & Fades", "Beard Trim & Shave", "Kids Cuts"]},
        {"slug": "nails", "name": "Nails", "icon": "💅", "image": "images/nails.jpg",
         "price_label": "Manicure", "price": 600,
         "items": ["Manicure & Pedicure", "Gel & Acrylics", "Nail Art"]},
        {"slug": "makeup", "name": "Makeup", "icon": "💄", "image": "images/makeup.jpg",
         "price_label": "Makeup", "price": 1500,
         "items": ["Makeup (Bridal, Graduation, Everyday Glam)", "Eyebrows Shaping & Tinting",
                   "Eyelash Extension"]},
        {"slug": "spa", "name": "Spa", "icon": "🧖‍♀️", "image": "images/spa.jpg",
         "price_label": "Facials", "price": 1200,
         "items": ["Facial Treatment", "Body Scrub", "Massage (Head / Shoulder)", "Waxing"]},
        {"slug": "bridal", "name": "Bridal", "icon": "👰", "image": "images/bridal.jpg",
         "price_label": "Full package", "price": 8000,
         "items": ["Full Bridal: Hair + Makeup + Nails + Facial"]},
    ]
    return render(request, "services.html", {"services": services})

def about(request):
    return render(request, "about.html")
def contact(request):
    return render(request, "contact.html")