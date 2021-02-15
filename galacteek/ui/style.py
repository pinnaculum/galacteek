
from PyQt5.QtWidgets import QStyle
from PyQt5.QtWidgets import QProxyStyle

from galacteek import cached_property
from galacteek.config import cGet


class GalacteekStyle(QProxyStyle):
    """
    Galacteek UI style (configurable)

    The configuration and the properties are cached for fast lookup
    (will need restart for changes to take effect)
    """
    def __init__(self, baseStyle='Fusion'):
        super().__init__(baseStyle)

    @cached_property
    def cStyle(self):
        sType = cGet('styles.galacteek.styleType',
                     mod='galacteek.ui')
        if not sType:
            sType = 'desktopGeneric'

        return cGet(f'styles.galacteek.{sType}',
                    mod='galacteek.ui')

    @cached_property
    def cToolBarIconSize(self):
        return self.cStyle.metrics.toolBarIconSize

    @cached_property
    def cToolBarItemMargin(self):
        return self.cStyle.metrics.toolBarItemMargin

    @cached_property
    def cToolBarItemSpacing(self):
        return self.cStyle.metrics.toolBarItemSpacing

    @cached_property
    def cToolBarSeparatorExtent(self):
        return self.cStyle.metrics.toolBarSeparatorExtent

    @cached_property
    def cTabBarIconSize(self):
        return self.cStyle.metrics.tabBarIconSize

    @cached_property
    def cTbIconSize(self):
        return self.cStyle.metrics.toolBarIconSize

    @cached_property
    def cTextCursorWidth(self):
        return self.cStyle.metrics.textCursorWidth

    @cached_property
    def cScrollBarExtent(self):
        return self.cStyle.metrics.scrollBarExtent

    @cached_property
    def cButtonDefaultIconSize(self):
        return self.cStyle.metrics.buttonDefaultIconSize

    def pixelMetric(self, metric, option, widget):
        if metric == QStyle.PM_ToolBarIconSize:
            return self.cToolBarIconSize
        elif metric == QStyle.PM_ToolBarSeparatorExtent:
            return self.cToolBarSeparatorExtent
        elif metric == QStyle.PM_TextCursorWidth:
            return self.cTextCursorWidth
        elif metric == QStyle.PM_TabBarIconSize:
            return self.cTabBarIconSize
        elif metric == QStyle.PM_ToolBarItemSpacing:
            return self.cToolBarItemSpacing
        elif metric == QStyle.PM_ToolBarItemMargin:
            return self.cToolBarItemMargin
        elif metric == QStyle.PM_ScrollBarExtent:
            return self.cScrollBarExtent
        elif metric == QStyle.PM_ButtonIconSize:
            return self.cButtonDefaultIconSize
        elif metric == QStyle.PM_TreeViewIndentation:
            return 25
        else:
            return super().pixelMetric(metric, option, widget)

    def styleHint(self, hint, option, widget, returnData):
        if hint == QStyle.SH_Menu_FlashTriggeredItem:
            return int(True)
        elif hint == QStyle.SH_ToolTip_WakeUpDelay:
            return 600
        elif hint == QStyle.SH_ToolTip_FallAsleepDelay:
            return 800
        else:
            return super().styleHint(hint, option, widget, returnData)
