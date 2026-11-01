import logging

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core import aws

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Idempotently creates the S3 evidence bucket and ensures private access block per D60."

    def handle(self, *args, **options):
        bucket_name = settings.EVIDENCE_BUCKET
        region = getattr(settings, "AWS_REGION", None) or getattr(
            settings, "AWS_DEFAULT_REGION", "ap-southeast-1"
        )
        s3 = aws.client("s3")

        bucket_exists = False
        try:
            s3.head_bucket(Bucket=bucket_name)
            bucket_exists = True
        except ClientError:
            pass

        if not bucket_exists:
            kwargs = {"Bucket": bucket_name}
            if region != "us-east-1":
                kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
            s3.create_bucket(**kwargs)
            self.stdout.write(self.style.SUCCESS(f"Created bucket {bucket_name} in {region}"))
        else:
            self.stdout.write(f"Bucket {bucket_name} already exists.")

        # Ensure public access block is fully enabled
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Configured PublicAccessBlock on {bucket_name}"))
