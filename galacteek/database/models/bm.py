from tortoise.models import Model
from tortoise import fields


class BitMessageMailBox(Model):
    TYPE_REGULAR = 0
    TYPE_ENC = 1

    id = fields.IntField(pk=True)

    bmAddress = fields.CharField(max_length=128, unique=True)

    # Label and nickname associated
    label = fields.CharField(max_length=32, unique=True)
    nickname = fields.CharField(max_length=32, null=True)
    fullname = fields.CharField(max_length=96, null=True)

    # Associated DID, if any
    did = fields.CharField(max_length=128, null=True)

    # Icon
    iconCid = fields.CharField(max_length=128, null=True)

    # Maildir type and path, relative to the root path where we store mailboxes
    mDirType = fields.IntField(default=TYPE_REGULAR)
    mDirRelativePath = fields.CharField(max_length=128)

    active = fields.BooleanField(default=True)
    default = fields.BooleanField(default=False)

    # Preferences
    prefs: fields.OneToOneRelation["BitMessageMailBoxPrefs"] = \
        fields.OneToOneField(
        'models.BitMessageMailBoxPrefs',
        on_delete=fields.CASCADE,
        related_name='prefs'
    )

    dateCreated = fields.DatetimeField(auto_now_add=True)
    dateALast = fields.DatetimeField(auto_now_add=True)


class BitMessageMailBoxPrefs(Model):
    id = fields.IntField(pk=True)

    # Sig
    signature = fields.CharField(max_length=512, null=True)

    # Default content-type when composing
    cContentType = fields.CharField(max_length=32, default='text/plain')
    markupType = fields.CharField(max_length=32, default='markdown')

    # Compose options
    cIgnoreNoSubject = fields.BooleanField(default=True)

    # Links options
    linksOpen = fields.BooleanField(default=True)


class BitMessageContactGroup(Model):
    id = fields.IntField(pk=True)

    # Group name
    name = fields.CharField(max_length=64, unique=True)


class BitMessageBlackList(Model):
    id = fields.IntField(pk=True)

    # Black-listed contact's BM address
    bmAddress = fields.CharField(max_length=128, unique=True)

    # Black-listed rule counter
    hitCount = fields.IntField(default=0)

    enabled = fields.BooleanField(default=True)
    dateCreated = fields.DatetimeField(auto_now_add=True)


class BitMessageContact(Model):
    id = fields.IntField(pk=True)

    # Contact's BM address
    bmAddress = fields.CharField(max_length=128, unique=True)

    # fullname
    fullname = fields.CharField(max_length=96)

    # Associated icon
    iconCid = fields.CharField(max_length=128, null=True)

    cSeparator = fields.CharField(max_length=3, default='')

    did = fields.CharField(max_length=256, null=True)

    dateCreated = fields.DatetimeField(auto_now_add=True)
    dateALast = fields.DatetimeField(auto_now_add=True)

    group = fields.ForeignKeyField(
        'models.BitMessageContactGroup',
        related_name='group',
        through='bm_contact_group',
        null=True,
        description='BM group')


class SoftwareVersionBeacon(Model):
    id = fields.IntField(pk=True)

    bmSourceAddress = fields.CharField(max_length=128)
    bmDestAddress = fields.CharField(max_length=128, null=True)

    content = fields.CharField(max_length=256, null=True)
    flags = fields.IntField(default=0)

    dateSent = fields.DatetimeField(auto_now_add=True)
