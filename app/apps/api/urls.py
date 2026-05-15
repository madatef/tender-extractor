from django.urls import path

from apps.api.views.tender_view import TenderExtractorView

urlpatterns = [
    path("tender-extractor/", TenderExtractorView.as_view(), name="tender-extractor"),
]
