import os
import sys

from omegaconf import OmegaConf
from omegaconf import dictconfig

from pathlib import Path

from galacteek.core import pkgResourcesRscFilename


class ConfigError(Exception):
    pass


def merge(*cfgs):
    return OmegaConf.merge(*cfgs)


def environment():
    return {
        'env': os.environ.get(
            'GALACTEEK_ENV', 'main'),
        'ethenv': os.environ.get(
            'GALACTEEK_ETHNETWORK_ENV', 'rinkeby'),
    }


def empty():
    return OmegaConf.create({})


def load(configPath: Path, envConf: dict = None) -> dictconfig.DictConfig:
    # global genvs, ethEnvs
    genvs = 'envs'
    ethEnvs = 'ethEnvs'

    envConf = envConf if envConf else environment()
    env = envConf['env']
    ethEnv = envConf['ethenv']

    try:
        base = empty()
        config = OmegaConf.load(str(configPath))

        envs = config.get(genvs, None)
        if envs:
            default = envs.get('default', None)
            if default:
                base = merge(base, default)

            if env in envs:
                base = merge(base, envs.get(env))
        genvs = config.get(ethEnvs, None)
        if genvs:
            default = genvs.get('default', None)
            if default:
                base = merge(base, default)

            if ethEnv in genvs:
                base = merge(base, genvs.get(ethEnv))
    except Exception as err:
        print(f'Error parsing config file {configPath}: {err}',
              file=sys.stderr)
        return None, None
    else:
        return config, base


def configFromFile(fpath: Path,
                   env_name: str = None) -> dictconfig.DictConfig:
    envConf = environment()

    # TODO: cache
    dpath = Path(pkgResourcesRscFilename(
        'galacteek.config.defaults',
        'config-default.yaml'
    ))

    top = empty()
    defaultsAll, defaults = load(str(dpath), envConf)

    configAll, config = load(str(fpath), envConf)

    if defaults:
        top = merge(top, defaults)

    if config:
        top = merge(config, top)

    if not top:
        return None

    return configAll, top
