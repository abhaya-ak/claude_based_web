import logging

from django.utils import timezone
from django.utils.text import slugify
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.core.exceptions import ConflictError
from apps.literacy.models import ContentStatus, EducationalGuide, Language, ReadabilityMode

logger = logging.getLogger(__name__)


def generate_unique_slug(title: str, instance_id=None) -> str:
    """
    Generates a URL-safe, lowercase, hyphen-delimited slug from title.
    Appends numeric suffixes (-2, -3, ...) if slug collisions exist.
    """
    base_slug = slugify(title)
    if not base_slug:
        base_slug = "guide"

    slug = base_slug
    counter = 2

    qs = EducationalGuide.objects.all()
    if instance_id:
        qs = qs.exclude(id=instance_id)

    while qs.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def create_guide(data: dict, author: User) -> EducationalGuide:
    """Creates a new EducationalGuide in DRAFT status."""
    title = data["title"]
    slug = generate_unique_slug(title)

    guide = EducationalGuide.objects.create(
        title=title,
        slug=slug,
        summary=data["summary"],
        body=data["body"],
        audience_groups=data.get("audience_groups", []),
        tactics=data.get("tactics", []),
        language=data.get("language", Language.EN),
        readability_mode=data.get("readability_mode", ReadabilityMode.STANDARD),
        status=ContentStatus.DRAFT.value,
        author=author,
    )
    return guide


def update_guide(guide: EducationalGuide, data: dict) -> EducationalGuide:
    """Updates guide content fields, re-slugifying if title changes."""
    if "title" in data and data["title"] != guide.title:
        guide.title = data["title"]
        guide.slug = generate_unique_slug(data["title"], instance_id=guide.id)

    for field in ["summary", "body", "audience_groups", "tactics", "language", "readability_mode"]:
        if field in data:
            setattr(guide, field, data[field])

    guide.save()
    return guide


def delete_guide(guide: EducationalGuide) -> None:
    """
    Deletes a guide if and only if it is in DRAFT status.
    Raises 409 Conflict if PUBLISHED or ARCHIVED per D112.
    """
    if guide.status != ContentStatus.DRAFT.value:
        raise ConflictError(
            detail="Only DRAFT guides can be deleted.",
            code="guide_not_draft",
        )
    guide.delete()


def publish_guide(guide: EducationalGuide) -> EducationalGuide:
    """
    Transitions guide to PUBLISHED status.
    Validates cardinality(audience_groups) >= 1.
    Sets published_at timestamp only on the first publication (invariant thereafter).
    """
    if not guide.audience_groups or len(guide.audience_groups) < 1:
        raise ValidationError(
            {"audience_groups": ["At least one audience group is required to publish."]}
        )

    guide.status = ContentStatus.PUBLISHED.value
    if guide.published_at is None:
        guide.published_at = timezone.now()

    guide.save()
    return guide


def unpublish_guide(guide: EducationalGuide) -> EducationalGuide:
    """Reverts a guide back to DRAFT status."""
    guide.status = ContentStatus.DRAFT.value
    guide.save()
    return guide


def archive_guide(guide: EducationalGuide) -> EducationalGuide:
    """Transitions a guide to ARCHIVED status."""
    guide.status = ContentStatus.ARCHIVED.value
    guide.save()
    return guide
