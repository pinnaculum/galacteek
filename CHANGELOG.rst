=========
CHANGELOG
=========

0.4.6
=====

- Implement ENS resolver (ens:// URLs are supported in the browser)
- Replace most asyncio.wait_for() calls by async_timeout (serious
  performance benefit here especially in the filemanager)
- General purpose database with aiosqlite
