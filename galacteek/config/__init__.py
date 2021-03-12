import asyncio
import attr
import inspect
import functools
from pathlib import Path

from omegaconf import OmegaConf
from omegaconf import dictconfig  # noqa

from PyQt5.QtCore import QTimer

from galacteek.core import pkgResourcesRscFilename
from galacteek.core import pkgResourcesListDir
from galacteek import log
from galacteek import ensure

from types import SimpleNamespace

from .util import configFromFile
from .util import environment
from .util import empty
from .util import dictDotLeaves


class NestedNamespace(SimpleNamespace):
    def __init__(self, dictionary, **kwargs):
        super().__init__(**kwargs)
        for key, value in dictionary.items():
            if isinstance(value, dict):
                self.__setattr__(key, NestedNamespace(value))
            else:
                self.__setattr__(key, value)


cCache = {}

configSaveRootPath = None
yamlExt = 'yaml'
configYamlName = f'config.{yamlExt}'


def cSetSavePath(path: Path):
    global configSaveRootPath
    global configSavePath

    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)

    configSaveRootPath = path

    log.debug(f'cSetSavePath: using {path}')


def gTranslate(name):
    return name.replace('galacteek', 'g')


def merge(*cfgs):
    return OmegaConf.merge(*cfgs)


def configSavePackage(pkgName: str):
    cEntry = regConfigFromPyPkg(pkgName)
    if cEntry:
        savePath = cEntry['path']
        savePath.parent.mkdir(parents=True, exist_ok=True)

        OmegaConf.save(cEntry['configAll'], str(savePath))


def regConfigFromFile(pkgName: str, fpath: str):
    global cCache

    eConf = cCache.get(pkgName, None)
    if eConf:
        return eConf

    if not fpath or not fpath.is_file():
        raise Exception(f'Config for {pkgName} does not exist')

    savePath = configSaveRootPath.joinpath(f'{pkgName}.{yamlExt}')

    cfgAll, cfg = configFromFile(fpath)
    if not cfg:
        return None

    if savePath.is_file():
        # Merge existing
        eCfgAll, eCfg = configFromFile(str(savePath))
        if eCfg:
            cfgAll = merge(cfgAll, eCfgAll)

    savePath.parent.mkdir(parents=True, exist_ok=True)

    try:
        del cfgAll['envs']['default']
    except:
        pass

    cCache[pkgName] = {
        'configAll': cfgAll,
        'path': savePath,
        'timer': None,
        'callbacks': []
    }
    OmegaConf.save(cfgAll, str(savePath))

    return cCache[pkgName]


def regConfigFromPyPkg(pkgName: str):
    global cCache

    if not pkgName:
        return None

    eConf = cCache.get(pkgName, None)
    if eConf:
        return eConf

    fpath = Path(pkgResourcesRscFilename(pkgName, configYamlName))

    if fpath.is_file():
        regConfigFromFile(pkgName, fpath)

    if 0:
        listing = pkgResourcesListDir(pkgName, '')
        for entry in listing:
            if entry == configYamlName:
                continue

            mod = entry.replace(f'.{yamlExt}', '')
            modName = f'{pkgName}.{mod}'
            fpath = Path(pkgResourcesRscFilename(pkgName, entry))

            if fpath.exists() and fpath.name.endswith(yamlExt):
                regConfigFromFile(modName, fpath)


def configForModule(mod: str):
    global cCache

    environ = environment()
    env = environ['env']

    eConf = cCache.get(mod, None)
    if not eConf:
        return

    return eConf['configAll']['envs'].get(env, None)


def configModLeafAttributes(pkgName: str):
    global cCache

    try:
        conf = configForModule(pkgName)
        return dictDotLeaves(OmegaConf.to_container(conf))
    except Exception:
        return []


def configModules():
    global cCache
    return cCache.keys()


def configLeafAttributes():
    global cCache

    for modName, cEntry in cCache.items():
        attrs = configModLeafAttributes(modName)

        for attribute in attrs:
            yield modName, attribute


def cAttr(mod, cfg, attr, value=None, merge=False):
    environ = environment()
    env = environ['env']

    conf = cfg['envs'].setdefault(env, empty())

    if value is not None:
        # Set
        try:
            OmegaConf.update(conf, attr, value, merge=merge)
        except Exception:
            log.debug(f'{mod}: cannot set value for attribute {attr}')
        else:
            configSavePackage(mod)
    else:
        # Get
        return OmegaConf.select(conf, attr)


def callerMod():
    try:
        frm = inspect.stack()[2]
        mod = inspect.getmodule(frm[0])
        return mod.__name__
    except Exception as err:
        # Unlikely
        log.debug(f'Cannot determine caller module: {err}')
        return None


def cGet(attr: str, mod=None):
    if not mod:
        mod = callerMod()

    cEntry = regConfigFromPyPkg(mod)
    if cEntry:
        return cAttr(mod, cEntry['configAll'], attr)


def cParentGet(attr: str):
    mod = callerMod()
    parentMod = '.'.join(mod.split('.')[:-1])

    cEntry = regConfigFromPyPkg(parentMod)
    if cEntry:
        return cAttr(parentMod, cEntry['configAll'], attr)


def cSet(attr: str, value, mod=None,
         merge=False,
         noCallbacks=False):
    cbDelay = 700

    if not mod:
        mod = callerMod()

    cEntry = regConfigFromPyPkg(mod)
    if cEntry:
        cAttr(mod, cEntry['configAll'], attr, value, merge=merge)

        def onTimeout(timer, cfgEntry):
            timer.stop()

            for callback in cfgEntry['callbacks']:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        ensure(callback())
                    else:
                        callback()
                except Exception:
                    cfgEntry['callbacks'].remove(callback)

                    # log.debug(f'{mod}: purged dead callback')
                    continue

        if not noCallbacks:
            if not cEntry['timer']:
                timer = QTimer()
                timer.timeout.connect(
                    functools.partial(onTimeout, timer, cEntry))
                timer.start(cbDelay)
                cEntry['timer'] = timer
            else:
                cEntry['timer'].stop()
                cEntry['timer'].start(cbDelay)


def cSetDefault(attr: str, value, mod):
    val = cGet(attr, mod=mod)

    if not val:
        cSet(attr, value, mod, noCallbacks=True)


def cParentSet(attr: str, value, merge=False):
    mod = callerMod()
    parentMod = '.'.join(mod.split('.')[:-1])

    return cSet(attr, value, mod=parentMod, merge=merge)


def cWidgetGet(widget: str, mod=None):
    return cGet(f'widgets.{widget}', mod=mod if mod else callerMod())


def cWidgetSetAttr(widget: str, attr, value, mod=None):
    cSet(f'widgets.{widget}.{attr}',
         value, mod=mod if mod else callerMod())


def cObjectGet(object: str, mod=None):
    return cGet(f'objects.{object}', mod if mod else callerMod())


def cQtClassConfigGet(qtClass: str):
    return cGet(f'qtClasses.{qtClass}', mod=callerMod())


def cClassConfigGet(cls: str):
    return cGet(f'classes.{cls}', mod=callerMod())


def cModuleSave():
    configSavePackage(callerMod())


@attr.s(auto_attribs=True)
class ModuleConfigContext:
    mCfg: dict = None

    def __enter__(self):
        return self.mCfg

    def __exit__(self, *a):
        pass


def cModuleContext(mod: str):
    cfg = configForModule(mod if mod else callerMod())
    if cfg:
        return ModuleConfigContext(mCfg=cfg)
    else:
        raise Exception(f'No config for module {mod}')


def configModRegCallback(callback, mod=None):
    global cCache

    eConf = cCache.get(mod if mod else callerMod())
    if eConf:
        eConf['callbacks'].append(callback)


def configModRmCallback(callback, mod=None):
    global cCache

    eConf = cCache.get(mod if mod else callerMod())
    if eConf:
        try:
            eConf['callbacks'].remove(callback)
        except Exception:
            pass


def initFromTable():
    from galacteek.config.table import cfgInitTable

    for pkg in cfgInitTable:
        log.debug(f'Config: initializing from package/module {pkg}')

        try:
            regConfigFromPyPkg(pkg)
        except Exception as err:
            log.debug(f'Failed to load config from package {pkg}: {err}')
            continue

    return True


class Configurable(object):
    configModuleName = None

    def __init__(self, parent=None, applyNow=False):
        super(Configurable, self).__init__()
        self.parent = parent

        if applyNow:
            self.cApply()

        if self.configModuleName:
            configModRegCallback(
                self.onConfigChanged,
                mod=self.configModuleName
            )

    def cApply(self):
        self.configApply(self.config())

    def config(self):
        if self.configModuleName:
            return configForModule(self.configModuleName)

        return None

    def onConfigChanged(self):
        self.configApply(self.config())

    def configApply(self, config):
        pass

    def __del__(self):
        if self.configModuleName:
            configModRmCallback(
                self.onConfigChanged,
                mod=self.configModuleName
            )
