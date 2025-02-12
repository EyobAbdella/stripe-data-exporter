from django.conf import settings
from django.apps import apps
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from googleapiclient.discovery import build
from .models import Export
from .utils import google_credentials

User = apps.get_model(settings.AUTH_USER_MODEL)


class ExportFilesSerializer(ModelSerializer):
    user = serializers.CharField()

    class Meta:
        model = Export
        fields = [
            "id",
            "user",
            "export_type",
            "file_name",
            "date_range",
            "columns",
            "sheet_id",
            "created_at",
        ]


class ExportSerializer(serializers.Serializer):
    export_type = serializers.CharField()
    file_name = serializers.CharField()
    date_range = serializers.CharField()
    columns = serializers.ListField(child=serializers.CharField())
    data = serializers.ListField()

    def create(self, validated_data):
        user_id = self.context.get("request").user.id
        columns = validated_data.get("columns", [])
        data = validated_data.pop("data", [])

        user = User.objects.filter(id=user_id).first()
        tokens = {
            "google_access_token": user.google_access_token,
            "google_refresh_token": user.google_refresh_token,
        }
        credentials = google_credentials(tokens)
        if not credentials:
            return None

        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()

        # Create  new google sheet
        sheet_body = {
            "properties": {"title": validated_data.get("file_name", "New Sheet")}
        }
        new_sheet = sheet.create(body=sheet_body).execute()
        sheet_id = new_sheet["spreadsheetId"]

        # Add data
        values = [columns] + data
        body = {"values": values}

        result = (
            sheet.values()
            .append(
                spreadsheetId=sheet_id,
                range="Sheet1",
                valueInputOption="RAW",
                body=body,
                insertDataOption="INSERT_ROWS",
            )
            .execute()
        )
        header_format_requests = {
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": 0,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": len(columns),
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {
                                    "bold": True,
                                    "foregroundColor": {
                                        "red": 1.0,
                                        "green": 0.0,
                                        "blue": 0.0,
                                    },
                                },
                                "backgroundColor": {
                                    "red": 0.9,
                                    "green": 0.9,
                                    "blue": 0.9,
                                },
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,backgroundColor)",
                    }
                }
            ]
        }

        sheet.batchUpdate(spreadsheetId=sheet_id, body=header_format_requests).execute()
        return Export.objects.create(
            user_id=user_id, sheet_id=sheet_id, **validated_data
        )
