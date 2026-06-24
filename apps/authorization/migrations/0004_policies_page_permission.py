from django.db import migrations


def create_policies_permission(apps, schema_editor):
    PageDefinition = apps.get_model('authorization', 'PageDefinition')
    PermissionDefinition = apps.get_model('authorization', 'PermissionDefinition')
    RoleGroup = apps.get_model('authorization', 'RoleGroup')
    RolePermission = apps.get_model('authorization', 'RolePermission')

    page, _ = PageDefinition.objects.update_or_create(
        code='policies.company',
        defaults={
            'module': 'policies', 'name': 'Policies',
            'url_name': 'policies:list', 'menu_order': 12,
            'is_menu_item': True, 'is_active': True,
        },
    )

    perm, _ = PermissionDefinition.objects.update_or_create(
        code='policies.company.manage',
        defaults={
            'module': 'policies', 'action': 'manage',
            'name': 'Manage policies', 'page': page, 'is_active': True,
        },
    )

    for role in RoleGroup.objects.filter(code='SYSTEM_ADMINS'):
        RolePermission.objects.update_or_create(
            role=role, permission=perm, defaults={'allow': True}
        )


def remove_policies_permission(apps, schema_editor):
    PermissionDefinition = apps.get_model('authorization', 'PermissionDefinition')
    PageDefinition = apps.get_model('authorization', 'PageDefinition')
    PermissionDefinition.objects.filter(code='policies.company.manage').delete()
    PageDefinition.objects.filter(code='policies.company').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('authorization', '0003_team_page_and_permissions'),
    ]

    operations = [
        migrations.RunPython(create_policies_permission, reverse_code=remove_policies_permission),
    ]
