from tortoise.models import Model
from tortoise import fields


class BitMessageMailBox(Model):
    TYPE_REGULAR = 0
    TYPE_ENC = 1

    id = fields.IntField(pk=True)

    bmAddress = fields.CharField(max_length=128, unique=True)
    mDirType = fields.IntField(default=0)

    # Label and nickname associated
    label = fields.CharField(max_length=32, unique=True)
    nickname = fields.CharField(max_length=32, null=True)
    fullname = fields.CharField(max_length=64, null=True)

    # Icon
    iconCid = fields.CharField(max_length=128, null=True)

    # Sig
    signature = fields.CharField(max_length=512, null=True)

    # Maildir path, relative to the root path where we store mailboxes
    mDirRelativePath = fields.CharField(max_length=128)

    active = fields.BooleanField(default=True)
    default = fields.BooleanField(default=False)

    dateCreated = fields.DatetimeField(auto_now_add=True)
    dateALast = fields.DatetimeField(auto_now_add=True)
