import importlib
import re
import traceback

from galacteek import log
from galacteek.config import cGet


def apimod():
    try:
        return importlib.import_module('openai')
    except Exception as err:
        log.warning(f'The openai library was not found: {err}')


def apiKeyValid(key: str) -> bool:
    return re.search(r'\s*(sk\-[a-zA-Z0-9]{48})',
                     key) is not None


def setApiKey(apiKey):
    openai = apimod()

    if openai:
        openai.api_key = apiKey


def isConfigured() -> bool:
    openai = apimod()

    if openai and isinstance(openai.api_key, str):
        return apiKeyValid(openai.api_key)


def reconfigure(apiKey: str):
    if apiKey and apiKeyValid(apiKey):
        setApiKey(apiKey)


def resetApiKey():
    setApiKey(None)


async def complete(prompt: str,
                   engine: str = 'text-davinci-003',
                   maxtokens: int = 2000,
                   n: int = 1,
                   temperature: float = -1):
    account = cGet('accounts.main',
                   mod='galacteek.ai.openai')

    try:
        openai = apimod()
        temp = temperature if (temperature >= 0 and temperature <= 2.0) else \
            account.params.temperature

        completion = await openai.Completion.acreate(
            engine=engine,
            prompt=prompt,
            max_tokens=maxtokens,
            n=n,
            stop=None,
            temperature=temp
        )
    except Exception:
        log.debug(traceback.format_exc())
    else:
        return completion


async def imageCreate(prompt: str,
                      engine: str = 'text-davinci-003',
                      n: int = 1,
                      rformat='b64_json',
                      **opts):
    try:
        openai = apimod()

        resp = await openai.Image.acreate(
            prompt=prompt,
            n=n,
            response_format=rformat,
            **opts
        )
    except Exception:
        log.debug(traceback.format_exc())
    else:
        return resp


async def imageVary(image,
                    n: int = 1,
                    rformat='b64_json',
                    **opts):
    try:
        openai = apimod()

        assert n in range(1, 11)

        resp = await openai.Image.acreate_variation(
            image=image,
            n=n,
            response_format=rformat,
            **opts
        )
    except AssertionError:
        return None
    except Exception:
        log.debug(traceback.format_exc())
    else:
        return resp
