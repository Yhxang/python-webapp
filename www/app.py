#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__='yhxang'

'''
async web application
'''

import logging; logging.basicConfig(level=logging.INFO)
import asyncio, os, json, time
from datetime import datetime
from aiohttp import web


async def index(request):
    return web.Response(text='<h1>awsome</h1>', headers={'content-type': 'text/html'})

app = web.Application()
app.add_routes([web.get('/', index)])
logging.info('server starded at http://172.20.12.171:9000')

web.run_app(app, host='0.0.0.0', port=9000)
