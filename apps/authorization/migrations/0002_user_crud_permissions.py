from django.db import migrations

def create_and_assign_permissions(apps, schema_editor):
    PageDefinition = apps.get_model('authorization', 'PageDefinition')
    PermissionDefinition = apps.get_model('authorization', 'PermissionDefinition')
    RoleGroup = apps.get_model('authorization', 'RoleGroup')
    RolePermission = apps.get_model('authorization', 'RolePermission')

    # Get admin.users page
    admin_users_page = PageDefinition.objects.filter(code='admin.users').first()

    # Create admin.users.update and admin.users.delete
    update_perm, _ = PermissionDefinition.objects.update_or_create(
        code='admin.users.update',
        defaults={
            'module': 'admin',
            'action': 'update',
            'name': 'Update users',
            'page': admin_users_page,
            'is_active': True,
        }
    )

    delete_perm, _ = PermissionDefinition.objects.update_or_create(
        code='admin.users.delete',
        defaults={
            'module': 'admin',
            'action': 'delete',
            'name': 'Delete users',
            'page': admin_users_page,
            'is_active': True,
        }
    )

    # Assign to default SYSTEM_ADMINS roles
    system_admin_roles = RoleGroup.objects.filter(code='SYSTEM_ADMINS')
    for role in system_admin_roles:
        RolePermission.objects.update_or_create(
            role=role,
            permission=update_perm,
            defaults={'allow': True}
        )
        RolePermission.objects.update_or_create(
            role=role,
            permission=delete_perm,
            defaults={'allow': True}
        )

def remove_permissions(apps, schema_editor):
    PermissionDefinition = apps.get_model('authorization', 'PermissionDefinition')
    PermissionDefinition.objects.filter(code__in=['admin.users.update', 'admin.users.delete']).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('authorization', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_and_assign_permissions, reverse_code=remove_permissions),
    ]
