from PyQt5.QtCore import QCoreApplication


def iLinkToQaToolbar():
    return QCoreApplication.translate(
        'BrowserTabForm',
        'Link to Quick Access toolbar'
    )


def iQuickAccessDockToolTip():
    return QCoreApplication.translate(
        'toolbarQa',
        '''<p><b>Quick Access Dock</b></p>
           <p>Drag and drop any IPFS content here that
           you want to have easy access to !</p>
        '''
    )


def iQuickAccessSetResourcePriority():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Set hashmark access priority'
    )


def iQuickAccessSetHigherResourcePriority():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Set higher access priority'
    )


def iQuickAccessSetLowerResourcePriority():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Set lower access priority'
    )


def iCreateQaMapping():
    return QCoreApplication.translate('BrowserTabForm',
                                      'Create quick-access mapping')
