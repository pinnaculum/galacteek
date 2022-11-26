import re
import sys
import attr
import subprocess
from pathlib import Path
import importlib

from PyQt5.QtGui import QPalette
from PyQt5.QtGui import QColor

from galacteek import log
from galacteek.core import pkgResourcesDirEntries
from galacteek.core import pkgResourcesRscFilename
from galacteek.core import runningApp


@attr.s(auto_attribs=True)
class ThemeColors:
    wBgColor: str = 'gray'
    wItemBgColor: str = 'gray'

    webEngineBackground: str = '#323232'
    webEngineBackgroundActive: str = '#FFFAF0'

    paletteLink: str = '#1976d2'
    paletteLinkVisited: str = '#2a5a89'


@attr.s(auto_attribs=True)
class Theme:
    themePath: Path = None
    name: str = None
    colors: ThemeColors = ThemeColors()

    styleModName: str = None

    styleBaseTemplate: str = None

    @property
    def cssPath(self):
        return self.themePath.joinpath('css')

    def apply(self, app):
        palette = QPalette(app.palette())
        palette.setColor(QPalette.Link,
                         QColor(self.colors.paletteLink))
        palette.setColor(QPalette.LinkVisited,
                         QColor(self.colors.paletteLinkVisited))
        app.setPalette(palette)


def run(*args):
    p = subprocess.Popen(*args, stdout=subprocess.PIPE)
    stdout, err = p.communicate()
    return stdout


def themesList():
    for name in pkgResourcesDirEntries(__name__):
        path = Path(pkgResourcesRscFilename('galacteek.ui.themes', name))
        if path.is_dir():
            yield name, path


def modSpecImport(name, path, sysModuleName=None):
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)

        if sysModuleName:
            sys.modules[sysModuleName] = module

        spec.loader.exec_module(module)

        return module
    except Exception:
        return None


def tmplSub(tmpl, varname, repl):
    return re.sub(rf'@{varname}@', repl, tmpl)


def themesCompileAll():
    commonPath = Path(pkgResourcesRscFilename(
        'galacteek.ui.themes', '_common'))

    for name, path in themesList():
        qrcPath = path.joinpath('theme.qrc')
        oPath = path.joinpath('theme_rc.py')
        initPath = path.joinpath('__init__.py')

        try:
            themeModule = modSpecImport(name, str(initPath))
            theme = themeModule.theme
            theme.themePath = path
        except Exception:
            continue

        if theme.styleBaseTemplate:
            qssPath = path.joinpath('galacteek.qss')
            tPath = commonPath.joinpath(theme.styleBaseTemplate)

            try:
                with open(str(tPath), 'rt') as fd:
                    tmpl = fd.read()
            except Exception:
                continue

            tmpl = tmplSub(tmpl, 'WIDGET_BGCOLOR',
                           theme.colors.wBgColor)
            tmpl = tmplSub(tmpl, 'WIDGET_ITEM_HOVER_BGCOLOR',
                           theme.colors.wItemBgColor)

            with open(str(qssPath), 'w+t') as fd:
                fd.write(tmpl)

        output = run([
            'pyrcc5',
            str(qrcPath),
            '-o',
            str(oPath)
        ])

        log.debug(output)


class ThemesManager:
    def __init__(self):
        self.app = runningApp()

    def onThemeChanged(self, path: str):
        tp = Path(path)
        self.themeApply(tp.name)

    def change(self, theme):
        self.themeApply(theme)

    def qssCommon(self):
        return self.app.readQSSFile(
            pkgResourcesRscFilename(
                'galacteek.ui.themes', 'common.qss'
            )
        )

    def themeApply(self, themeName: str, watch: bool = False):
        themeDir = pkgResourcesRscFilename('galacteek.ui.themes', themeName)
        if not themeDir:
            return False

        initPath = Path(themeDir).joinpath('__init__.py')
        rcPath = Path(themeDir).joinpath('theme_rc.py')
        rcDotPath = f'galacteek.ui.themes.{themeName}.theme_rc'

        try:
            themeModule = modSpecImport(themeName, str(initPath))
            modSpecImport('theme_rc', str(rcPath),
                          sysModuleName=rcDotPath)
        except Exception as err:
            log.debug(f'Error importing theme {themeName}: {err}')

        try:
            theme = themeModule.theme
        except Exception as err:
            log.debug(f'Invalid theme {themeName}: {err}')
            return False

        theme.themePath = Path(themeDir)
        theme.styleModName = rcDotPath

        sysName = self.app.system.lower()
        qssPath = f":/galacteek/ui/themes/{themeName}/galacteek.qss"
        qssPlatformPath = \
            f":/galacteek/ui/themes/{themeName}/galacteek_{sysName}.qss"  # noqa

        commonQss = self.qssCommon()
        mainQss = self.app.readQSSFile(qssPath)

        if not commonQss or not mainQss:
            log.debug(f'No main QSS for theme: {themeName}')
            return False

        self.app.setStyleSheet(commonQss + mainQss)

        theme.apply(self.app)

        self.app.theme = theme
        return True
