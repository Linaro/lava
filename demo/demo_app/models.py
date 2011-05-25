from django.db import models


class Message(models.Model):

    text = models.TextField()
