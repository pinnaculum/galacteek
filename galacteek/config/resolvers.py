import os
from yarl import URL
from omegaconf import OmegaConf


def gitlabAssetUrl(path: str):
    """
    OC resolver returning a gitlab release asset URL

    (deprecated by gitlabEasyAssetUrl)

    :param str path: Full path to the release asset on the gitlab instance
    """

    baseUrl = os.environ.get(
        'GALACTEEK_GITLAB_INSTANCE_URL',
        'https://gitlab.com'
    )

    if not path.startswith('/'):
        path = '/' + path

    return str(URL(baseUrl).with_path(path))


def gitlabEasyAssetUrl(user: str,
                       project: str,
                       tag: str,
                       asset: str):
    """
    OC resolver returning a gitlab release asset URL

    :param str user: GitLab user account
    :param str project: GitLab project name
    :param str tag: Release tag
    :param str asset: Filename of the asset in the gitlab release
    """
    baseUrl = os.environ.get(
        'GALACTEEK_GITLAB_INSTANCE_URL',
        'https://gitlab.com'
    )

    return str(URL(baseUrl).with_path(
        f'/{user}/{project}/-/releases/{tag}/downloads/{asset}'
    ))


OmegaConf.register_new_resolver("gitlab_easy_asset_url", gitlabEasyAssetUrl)
OmegaConf.register_new_resolver("gitlab_asset_url", gitlabAssetUrl)
