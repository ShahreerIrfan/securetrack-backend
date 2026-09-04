from accounts.models import CustomUser
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        'Set an existing account\'s role. createsuperuser leaves role at its '
        '"user" default, so a fresh superuser still lands on the User '
        'dashboard until it is promoted here.'
    )

    def add_arguments(self, parser):
        parser.add_argument('email')
        parser.add_argument(
            '--role',
            default=CustomUser.Role.ADMIN,
            choices=[role for role, _ in CustomUser.Role.choices],
            help='Role to assign (default: admin).',
        )

    def handle(self, *args, **options):
        email = options['email']
        role = options['role']

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            raise CommandError(f'No account with email "{email}".')

        previous = user.role
        user.role = role
        user.save(update_fields=['role'])

        self.stdout.write(self.style.SUCCESS(
            f'{email}: role "{previous}" -> "{role}". '
            'Log out and back in so the new role lands in a fresh JWT.',
        ))
