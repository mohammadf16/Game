from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Create default admin user for Number Hunt'

    def handle(self, *args, **options):
        username = 'admin'
        password = 'admin123'
        email = 'admin@numberhunt.com'
        
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'Admin user "{username}" already exists')
            )
            return
        
        # Create admin user
        admin_user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created admin user "{username}" with password "{password}"'
            )
        )
