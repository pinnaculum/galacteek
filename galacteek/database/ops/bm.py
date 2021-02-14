from tortoise.query_utils import Q

from galacteek import log

from galacteek.database.models.bm import BitMessageMailBox
from galacteek.database.models.bm import BitMessageMailBoxPrefs
from galacteek.database.models.bm import BitMessageContact
from galacteek.database.models.bm import BitMessageContactGroup

# BM


async def bmMailBoxList():
    return await BitMessageMailBox.all()


async def bmMailBoxCount():
    return await BitMessageMailBox.all().count()


async def bmMailBoxGetDefault():
    """
    Return the default BM account, if there's any
    """
    return await BitMessageMailBox.filter(
        default=True).prefetch_related('prefs').first()


async def bmMailBoxSetDefault(bmAddress: str,
                              mailbox: BitMessageMailBox = None):
    """

    Set the default BM account
    """

    mbox = mailbox if mailbox else await bmMailBoxGet(bmAddress)
    if mbox:
        try:
            await BitMessageMailBox.all().update(default=False)
            mbox.default = True
            await mbox.save()
        except Exception as err:
            log.debug(f'Could not set default BM account {bmAddress}: {err}')
            return False
        else:
            return True


async def bmMailBoxGet(bmAddress: str):
    return await BitMessageMailBox.filter(
        bmAddress=bmAddress).prefetch_related('prefs').first()


async def bmMailBoxRegister(bmAddress: str,
                            label: str,
                            mDirRelativePath: str,
                            default=False,
                            cContentType='text/plain',
                            cTextMarkup='markdown',
                            iconCid=None):
    try:
        prefs = BitMessageMailBoxPrefs(
            cContentType=cContentType,
            markupType=cTextMarkup
        )
        await prefs.save()

        mb = BitMessageMailBox(
            bmAddress=bmAddress,
            label=label,
            mDirRelativePath=mDirRelativePath,
            iconCid=iconCid,
            prefs_id=prefs.id
        )

        await mb.save()
        await mb.fetch_related('prefs')

        if default is True:
            await bmMailBoxSetDefault(
                bmAddress,
                mailbox=mb
            )

        return mb
    except Exception as cerr:
        log.debug(f'Could not create BM account {bmAddress}: {cerr}')


# Groups


# Contacts


async def bmContactAdd(bmAddress: str,
                       fullname: str,
                       separator: str = '',
                       groupName: str = '',
                       did=None):
    from galacteek.services.net.bitmessage import bmAddressValid

    try:
        assert bmAddressValid(bmAddress) is True
        assert len(fullname) in range(1, 96)

        group = None
        if groupName:
            group = await BitMessageContactGroup.filter(
                name=groupName).first()
            if not group:
                group = BitMessageContactGroup(name=groupName)
                await group.save()

        contact = BitMessageContact(
            bmAddress=bmAddress,
            fullname=fullname,
            cSeparator=separator,
            did=did,
            group=group
        )
        await contact.save()
    except Exception as cerr:
        log.debug(f'Could not add BM contact {bmAddress}: {cerr}')
    else:
        return contact


async def bmContactFilter(name: str,
                          separator: str = ''):
    return BitMessageContact.filter(
        Q(fullname__icontains=name) & Q(cSeparator=separator))


async def bmContactByName(name: str,
                          separator: str = ''):
    return await (await bmContactFilter(name, separator)).all()


async def bmContactByNameFirst(name: str,
                               separator: str = ''):
    return await (await bmContactFilter(name, separator)).first()


async def bmContactByAddr(bmAddr: str):
    return await BitMessageContact.filter(
        bmAddress=bmAddr).first()


async def bmContactAll():
    return await BitMessageContact.all()
