from tortoise.models import Model
from tortoise import fields


class IPFSRemotePinningService(Model):
    id = fields.IntField(pk=True)

    name = fields.CharField(max_length=256, unique=True)
    endpoint = fields.CharField(max_length=1024)
    key = fields.CharField(max_length=16384)

    priority = fields.IntField(default=0)

    enabled = fields.BooleanField(default=True)
    default = fields.BooleanField(default=False)

    dateAdded = fields.DatetimeField(auto_now_add=True)
