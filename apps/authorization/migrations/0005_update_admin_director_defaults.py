from django.db import migrations


def update_admin_director_defaults(apps, schema_editor):
    db = schema_editor.connection.alias
    RoleGroup = apps.get_model("authorization", "RoleGroup")
    PermissionDefinition = apps.get_model("authorization", "PermissionDefinition")
    RolePermission = apps.get_model("authorization", "RolePermission")

    # 1. Update SYSTEM_ADMINS permissions:
    # SYSTEM_ADMINS should only have permissions where the module is 'admin', 'audit', or 'authorization'
    admin_audit_auth_perms = list(
        PermissionDefinition.objects.using(db).filter(
            module__in=["admin", "audit", "authorization"]
        )
    )
    admin_audit_auth_ids = {p.id for p in admin_audit_auth_perms}

    for role in RoleGroup.objects.using(db).filter(code="SYSTEM_ADMINS"):
        # Delete any role permissions not in the allowed modules
        RolePermission.objects.using(db).filter(role=role).exclude(
            permission_id__in=admin_audit_auth_ids
        ).delete()
        
        # Ensure all allowed module permissions are granted
        for perm in admin_audit_auth_perms:
            RolePermission.objects.using(db).update_or_create(
                role=role,
                permission=perm,
                defaults={"allow": True}
            )

    # 2. Update DIRECTORS permissions:
    # DIRECTORS should have all permissions
    all_perms = list(PermissionDefinition.objects.using(db).all())
    for role in RoleGroup.objects.using(db).filter(code="DIRECTORS"):
        for perm in all_perms:
            RolePermission.objects.using(db).update_or_create(
                role=role,
                permission=perm,
                defaults={"allow": True}
            )


class Migration(migrations.Migration):

    dependencies = [
        ("authorization", "0004_policies_page_permission"),
    ]

    operations = [
        migrations.RunPython(update_admin_director_defaults, migrations.RunPython.noop),
    ]
