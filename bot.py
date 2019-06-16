# -*- coding: utf-8 -*-

from aiohttp import web, ClientSession

import logging
import os
import json
import pickle
import re

app = web.Application()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - [%(levelname)s]: %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S',
                    filename=os.path.join('.', 'booru_qq_bot.log'),
                    filemode='a')
logger = logging.getLogger(__name__)

API_BASE_URL = 'http://cqhttp:5700/'
PRE_BOORU_ABOUT_MSG = {}
BOT_API_URL_TEMPLATE = 'https://sakugabot.pw/api/posts/{0}'
AT_ME = '[CQ:at,qq=1262131302]'

HELP_MESSAGE = '使用指南：\n在群里at本账号同时附上sakugabooru的稿件链接，本账号将搜索是否存在微博gif数据， ' \
               '如果存在则发送gif地址到群里，否则报错。\n如果同一条信息里没有链接， ' \
               '则会使用聊天记录中最近的一条booru链接（小概率可能会找错，尽量使用第一种方法）。\n ' \
               'at时附上"-auto"可开启自动检测链接模式，若需取消附上"-no-auto"即可，默认开启。' \
               '自动模式下不会发送不存在的条目信息和错误信息，同时at模式仍然有效。\n' \
               'at本账号同时带上"-h"或"-help"可再次获取本帮助。'

# 设置初始化
if not os.path.exists('bot_auto_settings'):
    with open('bot_auto_settings', 'wb') as f:
        pickle.dump({}, f)
s_file = open('bot_auto_settings', 'rb')
AUTO_SETTINGS = pickle.load(s_file)
s_file.close()


async def receive(request):
    data = await request.read()
    data = json.loads(data.decode('utf8'))
    print(data)

    if data['post_type'] != 'message':
        return web.Response()
    if data['message_type'] != 'group':
        logger.error('非群消息-' + str(data))
        return web.Response()
    content = data['message']
    group_id = str(data['group_id'])
    logger.info('组[{0}]人[{1}][{2}]：{3}'.format(group_id, data['user_id'],
                                               data['sender']['card'] or data['sender']['nickname'], content))

    msg = None
    if 'sakugabooru.com/post/show/' in content:
        PRE_BOORU_ABOUT_MSG[group_id] = content
        if AUTO_SETTINGS.get(group_id, True) and AT_ME not in content:
            msg = await message_process(content, auto_model=True)
    if AT_ME in content:

        if '-h' in content or '-help' in content:
            msg = HELP_MESSAGE
        elif 'sakugabooru.com/post/show/' in content:
            msg = await message_process(content)
        elif '-no-auto' in content:
            msg = await auto_setting_process(data, undo=True)
        elif '-auto' in content:
            msg = await auto_setting_process(data)
        else:
            msg = await blank_at_process(group_id)

    if msg is None:
        return web.Response()
    else:
        logger.info('正在发送[{0}]：{1}'.format(group_id, msg))
        return web.json_response({
            'at_sender': False,
            'reply': msg
        })


async def message_process(message, auto_model=False):
    ids = re.findall(r'(?<=post/show/)(\d+)', message)
    if not ids:
        return None
    for id in ids:
        try:
            async with ClientSession() as session:
                async with session.get(BOT_API_URL_TEMPLATE.format(id)) as response:
                    if response.status == 404:
                        logger.info('404 of ' + id)
                        if not auto_model:
                            return '服务器中暂无此条目'
                    elif response.status == 200:
                        try:
                            j = await response.json()
                            return await gene_info_and_url(id, j)
                        except RuntimeError:
                            logger.error(id + ' 暂未有微博数据')
                            if not auto_model:
                                return '服务器中暂无此条目微博图片数据'
                    elif not auto_model:
                        logger.error(response.text)
                        return '服务器出错，请稍后再试'
        except Exception as e:
            logger.error(e)
            return '服务器出错，请稍后再试'


async def gene_info_and_url(id, post_info):
    gif_url = post_info['weibo']['img_url']
    if gif_url is None:
        raise RuntimeError('no img url')
    tags = post_info.get('tags', [])
    copyright, artist = [], []
    source = post_info.get('source', '/')
    for tag in tags:
        if tag['type'] == 3:
            copyright.append(tag['main_name'])
        if tag['type'] == 1:
            artist.append(tag['main_name'])
    return ''.join([
        str(id), ':\n', '，'.join(copyright), ' ' + source + ' ', '，'.join(artist), '\n' + gif_url
    ])


async def blank_at_process(group_id):
    content = PRE_BOORU_ABOUT_MSG.get(group_id, None)
    logger.info('处理空at from ' + group_id)
    if content:
        return await message_process(content)
    else:
        return '没有找到booru网址'


async def auto_setting_process(group_id, undo=False):
    if undo:
        AUTO_SETTINGS[group_id] = False
        logger.info('已取消自动模式-' + group_id)
        msg = '已取消自动模式'
    else:
        AUTO_SETTINGS[group_id] = True
        logger.info('自动检测设置成功-' + group_id)
        msg = '自动检测设置成功'
    with open('bot_auto_settings', 'wb') as f:
        pickle.dump(AUTO_SETTINGS, f)
    return msg


def setup_routes(app):
    app.router.add_post('/', receive)


if __name__ == '__main__':
    setup_routes(app)
    web.run_app(app, host='qqbot', port=5000)
