import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.core.jobs.registry import get_all_jobs, get_job, get_lock_id_for_job

logger = logging.getLogger(__name__)


def _discover_jobs():
    """Auto-discovers registered jobs across installed apps."""
    try:
        import apps.accounts.jobs  # noqa: F401
    except ImportError as e:
        logger.warning("Could not import accounts jobs: %s", e)


class Command(BaseCommand):
    help = "Executes registered background jobs protected by Postgres advisory locks (D51)."

    def add_arguments(self, parser):
        parser.add_argument("--job", help="Specific job name to run (runs all if omitted)")

    def handle(self, *args, **options):
        _discover_jobs()
        target_job_name = options.get("job")

        if target_job_name:
            job_func = get_job(target_job_name)
            if not job_func:
                raise CommandError(f"Job '{target_job_name}' is not registered.")
            jobs_to_run = {target_job_name: job_func}
        else:
            jobs_to_run = get_all_jobs()

        if not jobs_to_run:
            self.stdout.write(self.style.WARNING("No jobs registered to run."))
            return

        for name, fn in jobs_to_run.items():
            lock_id = get_lock_id_for_job(name)
            self._execute_with_advisory_lock(name, fn, lock_id)

    def _execute_with_advisory_lock(self, name, fn, lock_id):
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s);", [lock_id])
            acquired = cursor.fetchone()[0]

            if not acquired:
                self.stdout.write(self.style.WARNING(f"Job '{name}' is locked by another runner. Skipped."))
                return

            try:
                result = fn()
                self.stdout.write(self.style.SUCCESS(f"Job '{name}' completed: {result}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Job '{name}' failed with error: {e}"))
                logger.exception("Error executing scheduled job %s", name)
            finally:
                cursor.execute("SELECT pg_advisory_unlock(%s);", [lock_id])
