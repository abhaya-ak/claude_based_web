"""
Generate Mermaid ERD (docs/erd.md) from Django models.
Uses pure Django introspection without external dependencies.

Usage:
    cd backend
    python tools/generate_erd.py
"""

import os
import sys
from pathlib import Path

# Setup paths and Django environment
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.contrib.postgres.fields import ArrayField  # noqa: E402

APP_LABELS = [
    "accounts",
    "reports",
    "intel",
    "alerts",
    "broadcasts",
    "literacy",
    "scanner",
    "ops",
]


def get_field_type(field):
    """Return a Mermaid-safe type string (no spaces, no parentheses)."""
    if isinstance(field, ArrayField):
        base = field.base_field.get_internal_type()
        if "UUID" in base:
            return "uuid_array"
        return "string_array"

    internal_type = field.get_internal_type()
    mapping = {
        "UUIDField": "uuid",
        "CharField": "varchar",
        "TextField": "text",
        "BooleanField": "boolean",
        "IntegerField": "integer",
        "SmallIntegerField": "smallint",
        "PositiveSmallIntegerField": "smallint",
        "BigIntegerField": "bigint",
        "BigAutoField": "bigint",
        "DecimalField": "decimal",
        "DateTimeField": "timestamptz",
        "DateField": "date",
        "JSONField": "jsonb",
    }

    if field.is_relation and (field.many_to_one or field.one_to_one):
        target_pk = field.related_model._meta.pk
        return get_field_type(target_pk)

    return mapping.get(internal_type, internal_type.lower())


def generate_erd_content():
    """Introspect models across the 8 apps and format Mermaid ERD."""
    models = []
    for app_label in APP_LABELS:
        app_config = apps.get_app_config(app_label)
        models.extend(app_config.get_models())

    total_tables = len(models)

    relations = []
    entities = []

    for model in models:
        table_name = model._meta.db_table
        entity_lines = [f"    {table_name} {{"]

        for field in model._meta.fields:
            ftype = get_field_type(field)
            col = field.column

            mod = ""
            if field.primary_key:
                mod = " PK"
            elif field.is_relation and (field.many_to_one or field.one_to_one):
                mod = " FK"
            elif field.unique:
                mod = " UK"

            entity_lines.append(f"        {ftype} {col}{mod}")

            if field.is_relation and (field.many_to_one or field.one_to_one):
                parent_table = field.related_model._meta.db_table
                rel = "||--||" if field.one_to_one else "||--o{"
                relations.append(f"    {parent_table} {rel} {table_name} : \"{field.name}\"")

        entity_lines.append("    }")
        entities.append("\n".join(entity_lines))

    # Build markdown document
    lines = [
        "# ScamShield Cloud — Database Entity-Relationship Diagram",
        "",
        f"Total app tables: {total_tables}",
        "",
        "> Generated from Django models via `backend/tools/generate_erd.py`.",
        "",
        "```mermaid",
        "erDiagram",
    ]

    lines.extend(relations)
    lines.append("")
    lines.extend(entities)
    lines.append("```")
    lines.append("")

    return "\n".join(lines), total_tables


def main():
    docs_dir = backend_dir.parent / "docs"
    output_path = docs_dir / "erd.md"

    content, total_tables = generate_erd_content()
    output_path.write_text(content, encoding="utf-8")

    print(f"Generated ERD written to {output_path}")
    print(f"Total app tables introspected: {total_tables}")


if __name__ == "__main__":
    main()
