import os
from yarl import URL
from omegaconf import OmegaConf


def gitlabAssetUrl(path: str):
    baseUrl = os.environ.get(
        'GALACTEEK_GITLAB_INSTANCE_URL',
        'https://gitlab.com'
    )

    if not path.startswith('/'):
        path = '/' + path

    return str(URL(baseUrl).with_path(path))


OmegaConf.register_new_resolver("gitlab_asset_url", gitlabAssetUrl)
