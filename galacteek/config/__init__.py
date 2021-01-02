import os
import attr
import inspect
from pathlib import Path

from omegaconf import OmegaConf
from omegaconf import dictconfig  # noqa

from galacteek.core import pkgResourcesRscFilename
from galacteek.core import pkgResourcesListDir

from types import SimpleNamespace

from .util import configFromFile


class NestedNamespace(SimpleNamespace):
    def __init__(self, dictionary, **kwargs):
        super().__init__(**kwargs)
        for key, value in dictionary.items():
            if isinstance(value, dict):
                self.__setattr__(key, NestedNamespace(value))
            else:
                self.__setattr__(key, value)


gConf = OmegaConf.create({})
cCache = {}

configSaveRootPath = Path(os.getenv('HOME')).joinpath('.galacteek')
yamlExt = 'yaml'
configYamlName = f'config.{yamlExt}'


def cSetSavePath(path: Path):
    global configSaveRootPath
    global configSavePath

    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)

    configSaveRootPath = path


def gTranslate(name):
    return name.replace('galacteek', 'g')


def merge(*cfgs):
    return OmegaConf.merge(*cfgs)


def configSavePackage(pkgName: str):
    cEntry = regConfigFromPyPkg(pkgName)
    if cEntry:
        savePath = cEntry['path']
        savePath.parent.mkdir(parents=True, exist_ok=True)
        OmegaConf.save(cEntry['config'], str(savePath))


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
            # cfg = merge(eCfg, cfg)
            # cfg = merge(cfg, eCfg)
            cfgAll = merge(cfgAll, eCfgAll)

    savePath.parent.mkdir(parents=True, exist_ok=True)
    # OmegaConf.save(cfg, str(savePath))
    OmegaConf.save(cfgAll, str(savePath))

    cCache[pkgName] = {
        'configAll': cfgAll,
        'config': cfg,
        'path': savePath
    }

    return cCache[pkgName]


def regConfigFromPyPkg(pkgName: str):
    global cCache

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


def cAttr(mod, cfg, attr, value=None):
    cfgMove = cfg
    attrs = attr.split('.')
    if len(attrs) == 0:
        return cfg.get(attr)

    aCur = attrs.pop(0)
    while aCur:
        try:
            val = getattr(cfgMove, aCur)
        except Exception:
            return None

        try:
            aCur = attrs.pop(0)
        except:
            break

        if val:
            cfgMove = val

    if value:
        setattr(cfgMove, aCur, value)
        configSavePackage(mod)
    else:
        return getattr(cfgMove, aCur)


def callerMod():
    try:
        frm = inspect.stack()[2]
        mod = inspect.getmodule(frm[0])
        return mod.__name__
    except Exception:
        # Unlikely
        return None


def cGet(attr: str, mod=None):
    if not mod:
        mod = callerMod()

    cEntry = regConfigFromPyPkg(mod)
    if cEntry:
        return cAttr(mod, cEntry['config'], attr)


def cParentGet(attr: str):
    mod = callerMod()
    parentMod = '.'.join(mod.split('.')[:-1])

    cEntry = regConfigFromPyPkg(parentMod)
    if cEntry:
        return cAttr(parentMod, cEntry['config'], attr)


def cSet(attr: str, value, mod=None):
    if not mod:
        mod = callerMod()

    cEntry = regConfigFromPyPkg(mod)
    if cEntry:
        return cAttr(mod, cEntry['config'], attr, value)


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
