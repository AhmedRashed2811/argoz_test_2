from django.db import migrations


def create_team_permissions(apps, schema_editor):
    PageDefinition = apps.get_model('authorization', 'PageDefinition')
    PermissionDefinition = apps.get_model('authorization', 'PermissionDefinition')
    RoleGroup = apps.get_model('authorization', 'RoleGroup')
    RolePermission = apps.get_model('authorization', 'RolePermission')

    page, _ = PageDefinition.objects.update_or_create(
        code='admin.teams',
        defaults={
            'module': 'admin',
            'name': 'Sales Teams',
            'url_name': 'accounts:team_list',
            'menu_order': 11,
            'is_menu_item': True,
            'is_active': True,
        },
    )

    perm_defs = [
        ('admin.teams.access', 'access', 'Open sales teams page'),
        ('admin.teams.create', 'create', 'Create sales teams'),
        ('admin.teams.update', 'update', 'Update sales teams'),
        ('admin.teams.delete', 'delete', 'Deactivate sales teams'),
    ]
    perms = {}
    for code, action, name in perm_defs:
        p, _ = PermissionDefinition.objects.update_or_create(
            code=code,
            defaults={'module': 'admin', 'action': action, 'name': name,
                      'page': page, 'is_active': True},
        )
        perms[code] = p

    # Grant all four to every SYSTEM_ADMINS role (multi-company safe)
    for role in RoleGroup.objects.filter(code='SYSTEM_ADMINS'):
        for p in perms.values():
            RolePermission.objects.update_or_create(
                role=role, permission=p, defaults={'allow': True}
            )

    # Grant all four to SALES_OPERATION
    for role in RoleGroup.objects.filter(code='SALES_OPERATION'):
        for p in perms.values():
            RolePermission.objects.update_or_create(
                role=role, permission=p, defaults={'allow': True}
            )


def remove_team_permissions(apps, schema_editor):
    PermissionDefinition = apps.get_model('authorization', 'PermissionDefinition')
    PageDefinition = apps.get_model('authorization', 'PageDefinition')
    PermissionDefinition.objects.filter(code__in=[
        'admin.teams.access', 'admin.teams.create',
        'admin.teams.update', 'admin.teams.delete',
    ]).delete()
    PageDefinition.objects.filter(code='admin.teams').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('authorization', '0002_user_crud_permissions'),
    ]

    operations = [
        migrations.RunPython(create_team_permissions, reverse_code=remove_team_permissions),
    ]
