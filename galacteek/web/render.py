import asyncio
import functools
import jinja2, jinja2.exceptions

from galacteek import log
from galacteek.ipfs.wrappers import ipfsOp, ipfsOpFn

def defaultEnv():
    return jinja2.Environment(
	loader=jinja2.PackageLoader('galacteek', 'templates'),
	autoescape=jinja2.select_autoescape(['html', 'xml']))

@ipfsOpFn
async def ipfsRender(op, tmplname, **kw):
    env = defaultEnv()
    loop = kw.pop('loop', None)

    tmpl = env.get_template(tmplname)
    if not tmpl:
        raise Exception('template not found')

    try:
        loop = loop if loop else asyncio.get_event_loop()
        data = await loop.run_in_executor(None, functools.partial(tmpl.render, **kw))
        ent = await op.client.add_str(data)
    except Exception as e:
        log.debug('Could not render web template {0}'.format(tmplname))
        return None
    else:
        return ent['Hash']
