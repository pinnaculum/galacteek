from tortoise.models import Model
from tortoise import fields


class BrowserFeaturePermission(Model):
    PERM_DENY = 0
    PERM_ALLOW = 1

    id = fields.IntField(pk=True)

    url = fields.CharField(max_length=1024)
    featureCode = fields.IntField()
    permission = fields.IntField(default=0)

    dateAdded = fields.DatetimeField(auto_now_add=True)
    dateActiveUntil = fields.DatetimeField(null=True)
