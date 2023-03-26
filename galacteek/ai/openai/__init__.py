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
                   temperature: int = -1):
    account = cGet('accounts.main',
                   mod='galacteek.ai.openai')

    try:
        openai = apimod()

        completion = await openai.Completion.acreate(
            engine=engine,
            prompt=prompt,
            max_tokens=maxtokens,
            n=1,
            stop=None,
            temperature=account.params.temperature
        )
    except Exception:
        log.debug(traceback.format_exc())
    else:
        return completion


async def image(prompt: str,
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
