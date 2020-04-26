from tortoise.models import Model
from tortoise import fields


class AtomFeed(Model):
    id = fields.IntField(pk=True)

    url = fields.CharField(max_length=1024, unique=True)
    scheme = fields.CharField(null=True, max_length=32)
    feed_id = fields.CharField(null=True, max_length=256)
    autopin_entries = fields.BooleanField(default=True)
    datecreated = fields.DatetimeField(auto_now_add=True)


class AtomFeedHistory(Model):
    id = fields.IntField(pk=True)

    url = fields.CharField(max_length=1024, unique=True)
    scheme = fields.CharField(null=True, max_length=32)
    feed_id = fields.CharField(null=True, max_length=256)
    autopin_entries = fields.BooleanField(default=True)
    datecreated = fields.DatetimeField(auto_now_add=True)

    fh_atomfeed = fields.ForeignKeyField(
        'models.AtomFeed',
        related_name='fh_atomfeed',
        through='atomfeedhistory_feed')


class AtomFeedEntry(Model):
    id = fields.IntField(pk=True)

    entry_id = fields.CharField(max_length=1024, unique=True)
    status = fields.IntField(default=0)
    datepublished = fields.DatetimeField(auto_now_add=True)

    fe_atomfeed = fields.ForeignKeyField(
        'models.AtomFeed',
        related_name='fe_atomfeed',
        through='atomfeedhistory_feed')
