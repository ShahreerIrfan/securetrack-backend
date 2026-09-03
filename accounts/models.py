from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ANALYST = 'analyst', 'Analyst'
        DEVELOPER = 'developer', 'Developer'
        ADMIN = 'admin', 'Admin'

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)

    def __str__(self):
        return self.username
