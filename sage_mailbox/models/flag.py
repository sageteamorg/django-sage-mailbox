from django.db import models


class Flag(models.Model):
    FLAG_CHOICES = [
        ('SEEN', 'Seen'),
        ('ANSWERED', 'Answered'),
        ('FLAGGED', 'Flagged'),
        ('DELETED', 'Deleted'),
        ('DRAFT', 'Draft'),
        ('RECENT', 'Recent'),
    ]
    name = models.CharField(max_length=20, choices=FLAG_CHOICES)
