import json
from django.conf import settings
from django.contrib.auth import login
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import status
from urllib.parse import urlencode
from oauthlib.common import UNICODE_ASCII_CHARACTER_SET
from random import SystemRandom
from stripe import Webhook
from .models import User
import stripe
import requests
import jwt


@api_view(["GET"])
def handle_google_redirect(request):
    SCOPES = [
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
        "openid",
    ]

    rand = SystemRandom()
    state = "".join(rand.choice(UNICODE_ASCII_CHARACTER_SET) for _ in range(30))

    cache.set(state, True, timeout=500)

    redirect_uri = "http://127.0.0.1:8000/oauth/callback"
    # redirect_uri = "http://127.0.0.1:8000/oauth/status"

    params = {
        "response_type": "code",
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": " ".join(SCOPES),
        "state": state,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
    }

    query_params = urlencode(params)
    authorization_url = f"https://accounts.google.com/o/oauth2/auth?{query_params}"

    return Response(
        {
            "redirect": authorization_url,
            "state": params.get("state"),
        }
    )


@api_view(["GET"])
def handle_google_callback(request):
    code = request.GET.get("code")
    state = request.GET.get("state")
    error = request.GET.get("error")

    if error:
        return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

    if not code or not state:
        return Response(
            {"error": "code and state are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not cache.get(state):
        return Response(
            {"error": "Invalid or expired state."}, status=status.HTTP_400_BAD_REQUEST
        )
    cache.delete(state)

    redirect_uri = "http://127.0.0.1:8000/oauth/callback"
    token_endpoint = "https://oauth2.googleapis.com/token"

    data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    response = requests.post(token_endpoint, data=data)
    if not response.ok:
        return Response(
            {"error": "Failed to exchange authorization code for tokens."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tokens = response.json()

    id_token = tokens.get("id_token")

    if not id_token:
        return Response(
            {"error": "ID token is missing in the response."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    decoded_id_token = jwt.decode(id_token, options={"verify_signature": False})
    email = decoded_id_token.get("email")
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    user = User.objects.filter(email=email).first()

    if user is None:
        user = User.objects.create(
            email=email,
            google_access_token=access_token,
            google_refresh_token=refresh_token,
        )

    login(request, user)

    user.state = state
    user.save()
    return Response(
        {"detail": "Successfully Authenticated."}, status=status.HTTP_200_OK
    )


@api_view(["GET"])
@csrf_exempt
def verify_state(request):
    payload_data = request.headers.get("X-Payload-Data")
    sig_header = request.headers.get("Stripe-Signature")
    state = request.GET.get("state")
    if not payload_data or not sig_header:
        return Response({"error": "Missing payload or signature header"}, status=400)

    try:
        payload = payload_data.encode("utf-8")

        event = Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_APP_SECRET,
        )

        payload_json = json.loads(payload_data)
        user_id = payload_json.get("user_id")
        account_id = payload_json.get("account_id")
        try:
            user = User.objects.get(state=state)
            user.stripe_account_id = account_id
            user.stripe_user_id = user_id
            user.state = None
            user.save()
        except User.DoesNotExist:
            return Response(
                {"message": "unauthorized"}, status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = RefreshToken.for_user(user)
        token = TokenObtainPairSerializer().get_token(user)
        return Response(
            {
                "access_token": str(token.access_token),
                "refresh_token": str(refresh),
            },
            status=status.HTTP_200_OK,
        )

    except ValueError as e:
        return Response(
            {"error": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST
        )

    except stripe.error.SignatureVerificationError as e:
        return Response(
            {"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST
        )

    except Exception as e:
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
