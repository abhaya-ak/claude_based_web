from django.db import migrations

TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION fn_audit_append_only()
RETURNS TRIGGER AS $$
BEGIN
    IF current_setting('scamshield.audit_purge_allowed', true) = 'on' THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        ELSE
            RETURN NEW;
        END IF;
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF (OLD.actor_id IS NOT NULL AND NEW.actor_id IS NULL)
           AND (NEW.id IS NOT DISTINCT FROM OLD.id)
           AND (NEW.occurred_at IS NOT DISTINCT FROM OLD.occurred_at)
           AND (NEW.actor_ip_hash IS NOT DISTINCT FROM OLD.actor_ip_hash)
           AND (NEW.event_type IS NOT DISTINCT FROM OLD.event_type)
           AND (NEW.severity IS NOT DISTINCT FROM OLD.severity)
           AND (NEW.target_type IS NOT DISTINCT FROM OLD.target_type)
           AND (NEW.target_id IS NOT DISTINCT FROM OLD.target_id)
           AND (NEW.metadata IS NOT DISTINCT FROM OLD.metadata)
           AND (NEW.request_id IS NOT DISTINCT FROM OLD.request_id) THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'ops_systemauditlog is append-only: UPDATE is prohibited';
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'ops_systemauditlog is append-only: DELETE requires authorized retention purge';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_append_only
BEFORE UPDATE OR DELETE ON ops_systemauditlog
FOR EACH ROW
EXECUTE FUNCTION fn_audit_append_only();
"""

REVERSE_TRIGGER_SQL = """
DROP TRIGGER IF EXISTS trg_audit_append_only ON ops_systemauditlog;
DROP FUNCTION IF EXISTS fn_audit_append_only();
"""


class Migration(migrations.Migration):

    dependencies = [
        ("ops", "0003_report_track_failed"),
    ]

    operations = [
        migrations.RunSQL(
            sql=TRIGGER_SQL,
            reverse_sql=REVERSE_TRIGGER_SQL,
        ),
    ]
