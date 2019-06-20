=========
CHANGELOG
=========

0.4.6
=====

- Implement ENS resolver (ens:// URLs are supported in the browser)
- Replace most asyncio.wait_for() calls by async_timeout (performance)
- General purpose database (URL history for now) with aiosqlite
- Add a PIN button in the image viewer
