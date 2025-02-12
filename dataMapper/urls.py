from django.urls import path
from rest_framework import routers
from .views import ExportViewSet

router = routers.SimpleRouter()
router.register(r"exports", ExportViewSet, basename="Export")

urlpatterns = router.urls
