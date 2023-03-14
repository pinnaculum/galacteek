from PyQt5.QtCore import QCoreApplication

from .blackhole import iDagView


def iClipboardEmpty():
    return QCoreApplication.translate(
        'ClipboardManager',
        'No valid IPFS CID/path in the clipboard')


def iClipboardStackItemsCount(count):
    return QCoreApplication.translate(
        'ClipboardManager',
        '{} item(s) in the clipboard stack').format(count)


def iCopyCIDToClipboard():
    return QCoreApplication.translate(
        'FileManagerForm',
        "Copy CID to clipboard")


def iCopiedToClipboard():
    return QCoreApplication.translate(
        'FileManagerForm',
        'Copied to clipboard')


def iCopyPathToClipboard():
    return QCoreApplication.translate(
        'FileManagerForm',
        "Copy full path to clipboard")


def iCopyPubGwUrlToClipboard():
    return QCoreApplication.translate(
        'FileManagerForm',
        "Copy public gatewayed URL to clipboard (ipfs.io)")


def iCopySpGwUrlToClipboard():
    return QCoreApplication.translate(
        'FileManagerForm',
        "Copy gatewayed URL to clipboard (Specific Gateway)")


def iCopySpGwUrlToClipboardIpns():
    return QCoreApplication.translate(
        'FileManagerForm',
        "Copy gatewayed URL to clipboard (IPNS URL)")


def iCopySpGwUrlToClipboardCustom(msg: str):
    return QCoreApplication.translate(
        'FileManagerForm',
        "Copy gatewayed URL to clipboard ({0})").format(msg)


def iCopyToClipboard():
    return QCoreApplication.translate(
        'ClipboardManager',
        'Copy to clipboard')


def iClipboardNoValidAddress():
    return QCoreApplication.translate(
        'ClipboardManager',
        'No valid address for this item')


def iFromClipboard(path):
    return QCoreApplication.translate(
        'ClipboardManager',
        'Clipboard: browse IPFS path: {0}').format(path)


def iClipboardClearHistory():
    return QCoreApplication.translate(
        'ClipboardManager',
        'Clear clipboard history')


def iClipItemViewGraphAsTTL():
    return QCoreApplication.translate('ClipboardManager',
                                      'View graph as TTL (turtle)')


def iClipItemExplore():
    return QCoreApplication.translate('ClipboardManager',
                                      'Explore directory')


def iClipItemSubscribeToFeed():
    return QCoreApplication.translate('ClipboardManager',
                                      'Subscribe to Atom feed')


def iClipItemHashmark():
    return QCoreApplication.translate('ClipboardManager',
                                      'Hashmark')


def iClipItemPin():
    return QCoreApplication.translate('ClipboardManager',
                                      'Pin')


def iClipItemDownload():
    return QCoreApplication.translate('ClipboardManager',
                                      'Download')


def iClipItemIpldExplorer():
    return QCoreApplication.translate('ClipboardManager',
                                      'Run IPLD Explorer')


def iClipItemMarkupRocks():
    return QCoreApplication.translate('ClipboardManager',
                                      'Open with Markdown editor')


def iClipItemEditText():
    return QCoreApplication.translate('ClipboardManager',
                                      'Edit text file')


def iClipItemIcapsulesRegInstall():
    return QCoreApplication.translate('ClipboardManager',
                                      'Install capsules registry')


def iClipItemDagView():
    return iDagView()


def iClipboardHistory():
    return QCoreApplication.translate('ClipboardManager', 'Clipboard history')


def iClipItemBrowse():
    return QCoreApplication.translate('ClipboardManager',
                                      'Browse IPFS path')


def iClipItemOpen():
    return QCoreApplication.translate('ClipboardManager', 'Open')


def iClipItemOpenWithApp():
    return QCoreApplication.translate('ClipboardManager',
                                      'Open with application')


def iClipItemOpenWithDefaultApp():
    return QCoreApplication.translate('ClipboardManager',
                                      'Open with default system application')


def iClipItemSetCurrent():
    return QCoreApplication.translate('ClipboardManager',
                                      'Set as current clipboard item')


def iClipItemSetAsHome():
    return QCoreApplication.translate('ClipboardManager',
                                      'Set as homepage')


def iClipItemRemove():
    return QCoreApplication.translate('ClipboardManager',
                                      'Remove item')


def iClipItemSwitch(num):
    return QCoreApplication.translate(
        'ClipboardManager',
        'Switch to item {} in the stack').format(num)


def iClipboardStack():
    return QCoreApplication.translate('ClipboardManager',
                                      'Clipboard stack')


def iClipStackQrEncrypted():
    return QCoreApplication.translate(
        'ClipboardManager',
        'QR codes: encode clipboard stack to image (encrypted)')


def iClipStackQrPublic():
    return QCoreApplication.translate(
        'ClipboardManager',
        'QR codes: encode clipboard stack to image (clear)')
