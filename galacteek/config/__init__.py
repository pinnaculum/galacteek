import weakref
import attr
import inspect
from pathlib import Path

from omegaconf import OmegaConf
from omegaconf import dictconfig  # noqa

from galacteek.core import pkgResourcesRscFilename
from galacteek.core import pkgResourcesListDir
from galacteek import log

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
    OmegaConf.save(cfgAll, str(savePath))

    cCache[pkgName] = {
        'configAll': cfgAll,
        'config': cfg,
        'path': savePath,
        'callbacks': []
    }

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

    listing = pkgResourcesListDir(pkgName, '')
    for entry in listing:
        if entry == configYamlName:
            continue

        mod = entry.replace(f'.{yamlExt}', '')
        modName = f'{pkgName}.{mod}'
        fpath = Path(pkgResourcesRscFilename(pkgName, entry))

        if fpath.exists() and fpath.name.endswith(yamlExt):
            regConfigFromFile(modName, fpath)


def configModLeafAttributes(pkgName: str):
    global cCache

    eConf = cCache.get(pkgName, None)
    if not eConf:
        return

    conf = eConf['config']

    try:
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


def cAttr(mod, cfg, attr, value=None):
    environ = environment()
    env = environ['env']

    conf = cfg['envs'].setdefault(env, empty())

    if value is not None:
        # Set
        try:
            OmegaConf.update(conf, attr, value, merge=False)
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


def cSet(attr: str, value, mod=None):
    if not mod:
        mod = callerMod()

    cEntry = regConfigFromPyPkg(mod)
    if cEntry:
        cAttr(mod, cEntry['configAll'], attr, value)

        for ref in cEntry['callbacks']:
            try:
                callback = ref()
                callback()
            except Exception:
                pass


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
    if not mod:
        mod = callerMod()

    cEntry = regConfigFromPyPkg(mod)
    if cEntry:
        return ModuleConfigContext(mCfg=cEntry['config'])
    else:
        raise Exception(f'No config for module {mod}')


def configModRegCallback(callback):
    global cCache

    pkgName = callerMod()

    eConf = cCache.get(pkgName)
    if eConf:
        eConf['callbacks'].append(weakref.ref(callback))


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
