from PyQt5.QtCore import QCoreApplication

# Uncategorized translations, don't add anything here


def iNoStatus():
    return QCoreApplication.translate('GalacteekWindow', 'No status')


def iGeneralError(msg):
    return QCoreApplication.translate('GalacteekWindow',
                                      'General error: {0}').format(msg)


def iPubSubSniff():
    return QCoreApplication.translate('GalacteekWindow', 'Pubsub sniffer')


def iBrowse():
    return QCoreApplication.translate('GalacteekWindow', 'Browse')


def iHelp():
    return QCoreApplication.translate('GalacteekWindow', 'Help')


def iFollow():
    return QCoreApplication.translate('BrowserTabForm', 'Follow')


def iMinimized():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'galacteek was minimized to the system tray')


def iManual():
    return QCoreApplication.translate('GalacteekWindow', 'Manual')


def iFileManager():
    return QCoreApplication.translate('GalacteekWindow', 'File Manager')


def iTextEditor():
    return QCoreApplication.translate('GalacteekWindow', 'Editor')


def iKeys():
    return QCoreApplication.translate('GalacteekWindow', 'IPFS Keys')


def iSettings():
    return QCoreApplication.translate('GalacteekWindow', 'Settings')


def iConfigurationEditor():
    return QCoreApplication.translate('GalacteekWindow', 'Config Editor')


def iConfigurationEditorWarning():
    return QCoreApplication.translate(
        'GalacteekWindow',
        '<p>Hit <b>Enter</b> after changing a setting.</p>'
        '<p>Be careful with the settings you change. '
        'Start the application with <b>--config-defaults</b> '
        'if something goes wrong, to use the default '
        'configuration settings</p>')


def iEventLog():
    return QCoreApplication.translate('GalacteekWindow', 'Event Log')


def iNewProfile():
    return QCoreApplication.translate('GalacteekWindow', 'New Profile')


def iSwitchedProfile():
    return QCoreApplication.translate('GalacteekWindow',
                                      'Successfully switched profile')


def iDagViewer():
    return QCoreApplication.translate('GalacteekWindow', 'DAG viewer')


def iDagView():
    return QCoreApplication.translate('GalacteekWindow', 'DAG view')


def iParentDagView():
    return QCoreApplication.translate(
        'GalacteekWindow', 'DAG view (parent node)')


def iOpen():
    return QCoreApplication.translate('GalacteekWindow', 'Open')


def iNewBlogPost():
    return QCoreApplication.translate('GalacteekWindow', 'New blog post')


def iExploreDirectory():
    return QCoreApplication.translate('GalacteekWindow', 'Explore directory')


def iEditObject():
    return QCoreApplication.translate('GalacteekWindow', 'Edit')


def iEditInputObject():
    return QCoreApplication.translate('GalacteekWindow', 'Edit input')


def iDownload():
    return QCoreApplication.translate('GalacteekWindow', 'Download')


def iDownloads():
    return QCoreApplication.translate('GalacteekWindow', 'Downloads')


def iDownloadDirectory():
    return QCoreApplication.translate('GalacteekWindow', 'Download directory')


def iDownloadOpenDialog():
    return QCoreApplication.translate(
        'GalacteekWindow', 'Download or open IPFS object')


def iCancel():
    return QCoreApplication.translate('GalacteekWindow', 'Cancel')


def iChat():
    return QCoreApplication.translate('GalacteekWindow', 'Chat')


def iChatMessageNotification(channel, handle):
    return QCoreApplication.translate(
        'GalacteekWindow',
        '{0}: new message from {1}').format(channel, handle)


def iDelete():
    return QCoreApplication.translate('Galacteek', 'Delete')


def iRemove():
    return QCoreApplication.translate('Galacteek', 'Remove')


def iSeed():
    return QCoreApplication.translate('Galacteek', 'Seed')


def iShareFiles():
    return QCoreApplication.translate('Galacteek', 'Share files')


def iFileSharing():
    return QCoreApplication.translate('Galacteek', 'File sharing')


def iRemoveFileAsk():
    return QCoreApplication.translate(
        'Galacteek',
        'Are you sure you want to remove this file/directory ?'
    )


def iInvalidInput():
    return QCoreApplication.translate('GalacteekWindow', 'Invalid input')


def iKey():
    return QCoreApplication.translate('Galacteek', 'Key')


def iValue():
    return QCoreApplication.translate('Galacteek', 'Value')


def iTitle():
    return QCoreApplication.translate('GalacteekWindow', 'Title')


def iNoTitleProvided():
    return QCoreApplication.translate('GalacteekWindow',
                                      'Please specify a title')


def iFinished():
    return QCoreApplication.translate('GalacteekWindow', 'Finished')


def iDownloadOnly():
    return QCoreApplication.translate('GalacteekWindow', 'Download only')


def iZoomIn():
    return QCoreApplication.translate('GalacteekWindow', 'Zoom in')


def iZoomOut():
    return QCoreApplication.translate('GalacteekWindow', 'Zoom out')


def iQuit():
    return QCoreApplication.translate('GalacteekWindow', 'Quit')


def iRestart():
    return QCoreApplication.translate('GalacteekWindow', 'Restart')


def iClearHistory():
    return QCoreApplication.translate('GalacteekWindow', 'Clear history')


def iAtomFeeds():
    return QCoreApplication.translate('GalacteekWindow', 'Atom feeds')
