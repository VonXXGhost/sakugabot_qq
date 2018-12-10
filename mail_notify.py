from email.mime.text import MIMEText
from email.header import Header
from smtplib import SMTP_SSL
import requests
import time
import logging
import os

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - [%(levelname)s]: %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S',
                    filename=os.path.join('.', 'notify.log'),
                    filemode='a')
logger = logging.getLogger(__name__)
# qq邮箱smtp服务器
host_server = 'smtp.qq.com'
# sender_qq为发件人的qq号码
sender_qq = '582192766'
# pwd为qq邮箱的授权码
pwd = ''
# 发件人的邮箱
sender_mail = 'vonxxghost@foxmail.com'
# 监听状态
status_url = 'http://cqhttp:5700/get_status'


def send_mail_to_self(title, content):
    receiver = sender_mail
    # ssl登录
    smtp = SMTP_SSL(host_server)
    smtp.ehlo(host_server)
    smtp.login(sender_qq, pwd)

    msg = MIMEText(content, "plain", 'utf-8')
    msg["Subject"] = Header(title, 'utf-8')
    msg["From"] = sender_mail
    msg["To"] = receiver
    smtp.sendmail(sender_mail, receiver, msg.as_string())
    smtp.quit()


def listen_if_online():
    last_good = False
    while True:
        try:
            response = requests.get(status_url).json()
            good = response['data']['good']
            if good != last_good:
                logger.info('状态变化，现在为{}'.format(str(good)))
            if last_good and not good:  # 仅在好状态变为坏状态时发送
                send_mail_to_self('qqbot掉线了', 'RT')
                logger.info('掉线通知邮件已发送')
            last_good = good
        except Exception as e:
            logger.error(e)
        finally:
            time.sleep(60 * 5)


listen_if_online()
