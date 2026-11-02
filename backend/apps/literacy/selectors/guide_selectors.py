from django.db.models import Prefetch, QuerySet

from apps.literacy.models import ContentStatus, EducationalGuide, GuideAsset


def guides_for_tactics(tactics: list[str], language: str = "en") -> QuerySet[EducationalGuide]:
    """Retrieves published educational guides matching blind-spot tactics per Contract §3.8."""
    if not tactics:
        return EducationalGuide.objects.none()

    return (
        EducationalGuide.objects.filter(
            status=ContentStatus.PUBLISHED,
            tactics__overlap=tactics,
            language=language,
        )
        .prefetch_related(
            Prefetch("assets", queryset=GuideAsset.objects.order_by("sort_order"))
        )
        .order_by("-published_at", "title")
    )
