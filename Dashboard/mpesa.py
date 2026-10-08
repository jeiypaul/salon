import base64
import re
from datetime import datetime

import requests 
from django.conf import settings


class MpesaError(Exception):
    pass


def _base():
    if settings.MPESA_ENV == "production":
        return "https://api.safaricom.co.ke"
    return "https://sandbox.safaricom.co.ke"


def normalize_phone(raw):
    """0712345678 / +254712345678 / 254712345678 -> 254712345678, or None if invalid."""
    p = re.sub(r"[\s\-+]", "", raw or "")
    if re.fullmatch(r"0[17]\d{8}", p):
        p = "254" + p[1:]
    return p if re.fullmatch(r"254[17]\d{8}", p) else None


def _token():
    try:
        r = requests.get(
            f"{_base()}/oauth/v1/generate",
            params={"grant_type": "client_credentials"},
            auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
            timeout=20,
        )
        r.raise_for_status()
        return r.json()["access_token"]
    except (requests.RequestException, KeyError, ValueError):
        raise MpesaError("Could not connect to M-Pesa. Please try again in a moment.")


def _password(timestamp):
    raw = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
    return base64.b64encode(raw.encode()).decode()


def _post(path, payload):
    try:
        r = requests.post(
            f"{_base()}{path}",
            json=payload,
            headers={"Authorization": f"Bearer {_token()}"},
            timeout=30,
        )
        return r.json()
    except (requests.RequestException, ValueError):
        raise MpesaError("Could not reach M-Pesa. Please try again.")


def stk_push(phone, amount, account_ref):
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    callback = (
        f"{settings.MPESA_CALLBACK_BASE.rstrip('/')}"
        f"/mpesa/callback/{settings.MPESA_CALLBACK_SECRET}/"
    )
    data = _post("/mpesa/stkpush/v1/processrequest", {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": _password(ts),
        "Timestamp": ts,
        "TransactionType": settings.MPESA_TRANSACTION_TYPE,
        "Amount": int(amount),
        "PartyA": phone,
        "PartyB": settings.MPESA_PARTY_B,
        "PhoneNumber": phone,
        "CallBackURL": callback,
        "AccountReference": account_ref[:12],
        "TransactionDesc": "Salon booking",
    })
    if data.get("ResponseCode") != "0":
        raise MpesaError(
            data.get("errorMessage")
            or data.get("ResponseDescription")
            or "M-Pesa could not start the payment."
        )
    return data


def stk_query(checkout_request_id):
    """Ask Safaricom for the result when the callback hasn't arrived."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return _post("/mpesa/stkpushquery/v1/query", {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": _password(ts),
        "Timestamp": ts,
        "CheckoutRequestID": checkout_request_id,
    })