# -*- coding: utf-8 -*-

from aiohttp import web, ClientSession
from retrying import retry

import logging
import os
import json
import pickle
import re

import requests

app = web.Application()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - [%(levelname)s]: %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S',
                    filename=os.path.join('.', 'booru_qq_bot.log'),
                    filemode='a')
logger = logging.getLogger(__name__)

API_username = ''
API_password = ''
API_token = ''
API_refresh = ''

API_BASE_URL = 'http://cqhttp:5700/'
PRE_BOORU_ABOUT_MSG = {}
BOT_API_REFRESH_URL_TEMPLATE = 'https://sakugabot.pw/api/posts/{0}/refresh/'
BOT_API_URL_TEMPLATE = 'https://sakugabot.pw/api/posts/{0}/'
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
    logger.info('组[{0}]人[{1}]：{2}'.format(data['group_id'], data['user_id'], data['message']))

    content = data['message']
    group_id = str(data['group_id'])

    if 'sakugabooru.com/post/show/' in content:
        PRE_BOORU_ABOUT_MSG[group_id] = content
        if AUTO_SETTINGS.get(group_id, True) and AT_ME not in content:
            await message_process(content, data, auto_model=True)
    if AT_ME in content:

        if '-h' in content or '-help' in content:
            await send_help(data)
        elif 'sakugabooru.com/post/show/' in content:
            await message_process(content, data)
        elif '-no-auto' in content:
            await auto_setting_process(data, undo=True)
        elif '-auto' in content:
            await auto_setting_process(data)
        else:
            await blank_at_process(data)

    return web.Response()


async def message_process(message, data, auto_model=False):
    ids = re.findall(r'(?<=post/show/)(\d+)', message)
    if not ids:
        return
    for id in ids:
        try:
            async with ClientSession(headers={'Authorization': 'Bearer '+API_token}) as session:

                async with session.post(BOT_API_REFRESH_URL_TEMPLATE.format(id)) as response:
                    if response.status == 403 and API_token:    # token无效
                        logger.warning("当前token无效")
                        refresh_token()
                        await message_process(message, data, auto_model)
                        return
                    if response.status == 404:
                        logger.info('404 of ' + id)
                        if not auto_model:
                            await send_message('服务器中暂无此条目数据', data)
                    elif response.status == 200:
                        try:
                            await send_info_and_url(id, data)
                        except:
                            logger.error(id + ' 暂未有微博数据')
                            if not auto_model:
                                await send_message("服务器中暂无此条目数据", data)
                    elif not auto_model:
                        logger.error(response.text)
                        await send_message("服务器出错，请稍后再试", data)
        except Exception as e:
            logger.error(e)
            await send_message("服务器出错，请稍后再试", data)


async def send_info_and_url(id, data):
    # 使用刷新机制后需重新获取post_info
    async with ClientSession() as session:
        async with session.get(BOT_API_URL_TEMPLATE.format(id)) as response:
            if response.status == 200:
                post_info = await response.json()
            else:
                raise RuntimeError("can't get post info")

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
    text = ''.join([
        str(id), ':\n', '，'.join(copyright), ' ' + source + ' ', '，'.join(artist), '\n' + gif_url
    ])
    await send_message(text, data)


async def send_message(message, data):
    logger.info('正在发送[{0}]：{1}'.format(data['group_id'], message))
    await send_group_message(message, data['group_id'])
    logger.info('已发送[{0}]：{1}'.format(data['group_id'], message))


async def send_help(data):
    await send_message(HELP_MESSAGE, data)


@retry(stop_max_attempt_number=3, stop_max_delay=30000)
async def send_group_message(message, group_id):
    url = ''.join([API_BASE_URL, 'send_group_msg_async'])
    params = {
        'group_id': group_id,
        'message': message
    }
    async with ClientSession() as session:
        async with session.get(url, params=params) as res:
            res = await res.json()
            if res['status'] == 'failed':
                raise RuntimeError('Send message failed.group[{0}],message[{1}].'.format(group_id, message))


async def blank_at_process(data):
    content = PRE_BOORU_ABOUT_MSG.get(str(data['group_id']), None)
    logger.info('处理空at from ' + str(data['group_id']))
    if content:
        await message_process(content, data)
    else:
        await send_message("没有找到booru网址", data)


async def auto_setting_process(data, undo=False):
    name = str(data['group_id'])
    if undo:
        AUTO_SETTINGS[name] = False
        await send_message("已取消自动模式", data)
        logger.info("已取消自动模式-" + name)
    else:
        AUTO_SETTINGS[name] = True
        await send_message("自动检测设置成功", data)
        logger.info("自动检测设置成功-" + name)
    with open('bot_auto_settings', 'wb') as f:
        pickle.dump(AUTO_SETTINGS, f)


def setup_routes(app):
    app.router.add_post('/', receive)


def login():
    global API_token, API_refresh
    auth = requests.post('https://sakugabot.pw/api/token/', json={'username': API_username, 'password': API_password})
    if auth.status_code == 200:
        logger.info("登录sakugabot成功")
        API_token = auth.json()['access']
        API_refresh = auth.json()['refresh']
    elif 400 <= auth.status_code < 500:
        logger.error("登录失败，账户或密码错误？")
        exit(1)
    else:
        logger.error("登录失败:\n" + auth.text)
        exit(1)


def refresh_token():
    global API_token, API_refresh
    if API_refresh == '':
        logger.error("未登录，无法刷新token")
        exit(1)
    auth = requests.post('https://sakugabot.pw/api/token/refresh/', json={'refresh': API_refresh})
    if auth.status_code == 200:
        logger.info("token刷新成功")
        API_token = auth.json()['access']
    else:
        logger.error("token刷新失败:\n" + auth.text)
        exit(1)


if __name__ == '__main__':
    login()
    setup_routes(app)
    web.run_app(app, host='qqbot', port=5000)
