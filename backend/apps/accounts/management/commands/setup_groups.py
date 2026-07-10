from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission


class Command(BaseCommand):
    help = 'Create default user groups with permissions'

    def handle(self, *args, **options):
        groups = {
            'Researcher': [],
            'Procurement': [],
            'Editor': [],
            'Admin': [],  # Admin group gets all permissions
        }
        for name, perms in groups.items():
            group, created = Group.objects.get_or_create(name=name)
            if name == 'Admin':
                for p in Permission.objects.all():
                    group.permissions.add(p)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Group '{name}' {'created' if created else 'already exists'}"
                )
            )
        self.stdout.write(self.style.SUCCESS('All groups created successfully'))
