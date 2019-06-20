import asyncio
import aiosqlite
import sqlite3
import time
from datetime import datetime

from PyQt5.QtCore import QUrl

from galacteek import log
from galacteek.core.schemes import SCHEME_DWEB
from galacteek.core.schemes import SCHEME_IPFS
from galacteek.ipfs.cidhelpers import IPFSPath


schemaScript = '''
CREATE TABLE if not exists url_history_items
(id integer primary key, url text, scheme text,
rootcid text, rootcidv integer, ctime timestamp);

CREATE TABLE if not exists url_history_visits
(history_item_id integer, title text, atime timestamp);
'''


class SqliteDatabase:
    def __init__(self, dbPath):
        self._path = dbPath
        self._db = None

    @property
    def db(self):
        return self._db

    async def setup(self):
        try:
            self._db = await aiosqlite.connect(self._path)
            self._db.row_factory = aiosqlite.Row
        except:
            return False

        def adapt_datetime(ts):
            return time.mktime(ts.timetuple())

        sqlite3.register_adapter(datetime, adapt_datetime)

        try:
            await self.db.executescript(schemaScript)
        except Exception:
            log.debug('Error while executing schema script')
            return False

    async def historySearch(self, input):
        rows = []
        query = '''
        SELECT DISTINCT url, title, scheme, rootcid, rootcidv, id
        FROM url_history_visits
        INNER JOIN url_history_items ON
            url_history_items.id = url_history_visits.history_item_id
        WHERE url LIKE '%{input}%' OR title LIKE '%{input}%'
        COLLATE NOCASE
        ORDER BY atime desc'''

        async with self.db.execute(query.format(input=input)) as cursor:
            async for row in cursor:
                await asyncio.sleep(0)
                rows.append(row)
        return rows

    async def historyRecord(self, url, title):
        urlItemId = None
        existing = await self.historySearch(url)

        if len(existing) > 0:
            urlItemId = existing.pop()['id']
        else:
            qUrl = QUrl(url)
            scheme = qUrl.scheme() if qUrl.isValid() else ''

            rootcid = ''
            rootcidv = None

            if scheme in [SCHEME_DWEB, SCHEME_IPFS]:
                ipfsPath = IPFSPath(url)
                if ipfsPath.valid and ipfsPath.rootCid:
                    rootcid = str(ipfsPath.rootCid)
                    rootcidv = ipfsPath.rootCid.version

            cursor = await self.db.execute(
                """INSERT INTO url_history_items
                (url, scheme, rootcid, rootcidv, ctime)
                VALUES (?, ?, ?, ?, ?)""",
                (url, scheme, rootcid, rootcidv, datetime.now()))
            urlItemId = cursor.lastrowid

        cursor = await self.db.execute(
            """INSERT INTO url_history_visits
            (history_item_id, title, atime) VALUES (?, ?, ?)""",
            (urlItemId, title, datetime.now()))

        await self.db.commit()
        return True

    async def historyClear(self, before=None):
        if before:
            cursor = await self.db.execute(
                "DELETE FROM url_history_items WHERE ctime < {0}".format(
                    before))
            log.debug('Cleared {} history records'.format(cursor.rowcount))

            await self.db.execute(
                "DELETE FROM url_history_visits WHERE atime < {0}".format(
                    before))
        else:
            # Clear all
            cursor = await self.db.execute(
                'DELETE FROM url_history_items'
            )
            log.debug('Cleared {} history records'.format(cursor.rowcount))
            await self.db.execute(
                'DELETE FROM url_history_visits'
            )

        await self.db.commit()

    async def close(self):
        await self.db.close()
