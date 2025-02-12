from django.conf import settings
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from stripe import Webhook
from .models import Export
from .serializers import ExportFilesSerializer, ExportSerializer
import stripe


class ExportViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_id = self.request.user.id
        return Export.objects.filter(user_id=user_id)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ExportSerializer
        return ExportFilesSerializer

    def create(self, request, *args, **kwargs):
        payload_data = request.headers.get("X-Payload-Data")
        sig_header = request.headers.get("Stripe-Signature")
        if not sig_header:
            return Response(
                {"error": "Missing Stripe signature"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = payload_data.encode("utf-8")
            event = Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=settings.STRIPE_APP_SECRET,
            )
        except stripe.error.SignatureVerificationError:
            return Response(
                {"error": "Invalid Stripe signature"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return Response(
                {"error": "Webhook processing failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = ExportSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        export_instance = serializer.save()
        response_serializer = ExportFilesSerializer(export_instance)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
