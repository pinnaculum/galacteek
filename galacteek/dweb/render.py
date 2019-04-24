import asyncio
import functools
import jinja2
import jinja2.exceptions
from datetime import datetime

from galacteek import log
from galacteek.core import isoformat
from galacteek.ipfs.wrappers import ipfsOpFn


def tstodate(ts):
    try:
        date = datetime.fromtimestamp(ts)
    except TypeError:
        return ''
    else:
        return isoformat(date, timespec='seconds')


def defaultJinjaEnv():
    env = jinja2.Environment(
        loader=jinja2.PackageLoader('galacteek', 'templates'),
        autoescape=jinja2.select_autoescape(['html', 'xml']))
    env.filters['tstodate'] = tstodate
    return env


def renderWrapper(tmpl, **kw):
    try:
        data = tmpl.render(**kw)
    except Exception as err:
        log.debug('Error rendering jinja template',
                  exc_info=err)
        return None
    else:
        return data


async def renderTemplate(tmplname, loop=None, env=None, **kw):
    env = env if env else defaultJinjaEnv()
    loop = loop if loop else asyncio.get_event_loop()
    tmpl = env.get_template(tmplname)
    if not tmpl:
        raise Exception('template not found')

    data = await loop.run_in_executor(
        None, functools.partial(renderWrapper, tmpl, **kw)
    )
    return data


@ipfsOpFn
async def ipfsRender(op, tmplname, **kw):
    env = defaultJinjaEnv()
    loop = kw.pop('loop', None)

    tmpl = env.get_template(tmplname)
    if not tmpl:
        raise Exception('template not found')

    try:
        loop = loop if loop else asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None, functools.partial(tmpl.render, **kw)
        )
        ent = await op.client.add_str(data)
    except Exception:
        log.debug('Could not render web template {0}'.format(tmplname))
        return None
    else:
        return ent['Hash']
