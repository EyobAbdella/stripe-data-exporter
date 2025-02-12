from django.urls import path
from .views import verify_state, handle_google_callback, handle_google_redirect

urlpatterns = [
    path("redirect", handle_google_redirect),
    path("callback", handle_google_callback),
    path("verify/", verify_state),
]
