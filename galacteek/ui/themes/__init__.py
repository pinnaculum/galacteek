import attr
import subprocess
from pathlib import Path
import importlib
import sys

from galacteek import log
from galacteek.core import pkgResourcesDirEntries
from galacteek.core import pkgResourcesRscFilename
from galacteek.core import runningApp
from galacteek.core.fswatcher import FileWatcher


def run(*args):
    p = subprocess.Popen(*args, stdout=subprocess.PIPE)
    stdout, err = p.communicate()
    return stdout


def themesList():
    for name in pkgResourcesDirEntries(__name__):
        path = Path(pkgResourcesRscFilename('galacteek.ui.themes', name))
        if path.is_dir():
            yield name, path


def themesCompileAll():
    for name, path in themesList():
        # fp = pkgResourcesRscFilename('galacteek.ui.themes', dir)

        qrcPath = path.joinpath('style.qrc')
        oPath = path.joinpath('style_rc.py')

        output = run([
            'pyrcc5',
            str(qrcPath),
            '-o',
            str(oPath)
        ])

        log.debug(output)


def modSpecImport(name, path):
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        return module
    except Exception:
        return None


class ThemesManager:
    def __init__(self):
        self.app = runningApp()
        self.fsWatcher = FileWatcher()

        self.fsWatcher.pathChanged.connect(self.onThemeChanged)

    def onThemeChanged(self, path: str):
        tp = Path(path)
        self.themeApply(tp.name)

        # self.app.repolishWidget(self.app.mainWindow)

    def change(self, theme):
        self.themeApply(theme)

    def themeApply(self, theme):
        libFontsPath = pkgResourcesRscFilename(
            'galacteek.ui.themes', 'fonts.qss'
        )

        themeDir = pkgResourcesRscFilename('galacteek.ui.themes', theme)
        if not themeDir:
            return False

        initPath = Path(themeDir).joinpath('__init__.py')
        rcPath = Path(themeDir).joinpath('style_rc.py')

        try:
            if 0:
                themeModule = importlib.import_module(
                    f'galacteek.ui.themes.{theme}'
                )

                importlib.import_module(
                    f'galacteek.ui.themes.{theme}.style_rc'
                )

            themeModule = modSpecImport(theme, str(initPath))
            modSpecImport('style_rc', str(rcPath))
        except Exception as err:
            log.debug(f'Error importing theme {theme}: {err}')

        try:
            style = themeModule.style
        except Exception:
            style = None

        sysName = self.app.system.lower()
        qssPath = f":/galacteek/ui/themes/{theme}/galacteek.qss"
        qssPlatformPath = \
            f":/galacteek/ui/themes/{theme}/galacteek_{sysName}.qss"

        fontsQss = self.app.readQSSFile(libFontsPath)

        mainQss = self.app.readQSSFile(qssPath)
        pQss = self.app.readQSSFile(qssPlatformPath)

        qss = fontsQss + mainQss

        if pQss:
            self.app.setStyleSheet(qss + '\n' + pQss)
        else:
            self.app.setStyleSheet(qss)

        if style:
            self.app.setStyle(style)

        self.fsWatcher.watch(themeDir)
        return True


@attr.s(auto_attribs=True)
class Theme:
    name: str = None
