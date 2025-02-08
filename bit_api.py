import datetime
import time

import requests
from logger import Logger

request = requests.session()
url = "http://127.0.0.1:54347"
log = Logger()

def openBrowser(id):  # 打开窗口
    headers = {'id': id}
    res = request.post(f"{url}/browser/open", json=headers).json()
    log.logger.info(f'打开browser:{res}')
    return res


def closeBrowser(id):  # 关闭窗口
    headers = {'id': f'{id}'}
    res = request.post(f"{url}/browser/close", json=headers).json()
    log.logger.info(f'关闭browser:{res}')
    time.sleep(5)


def get_all_browser(page, pageSize):
    headers = {'page': page, 'pageSize': pageSize}
    res = request.post(f"{url}/browser/list", json=headers).json()
    # log.logger.info(f'所有browser:{res}')
    return res['data']['list']


def get_window_detail(id):
    headers = {'id': id}
    res = request.post(f"{url}/browser/detail", json=headers).json()
    # log.logger.info(f'所有browser:{res}')
    return res


def get_id_by_name(user_name):
    page = 0
    pageSize = 100
    all_browser = []
    browser_list = get_all_browser(page, pageSize)
    all_browser.append(browser_list)
    while len(browser_list) == pageSize:
        page = page + 1
        print(page)
        browser_list = get_all_browser(page, pageSize)
        all_browser.append(browser_list)
    for b in browser_list:
        if user_name == b['remark']:
            return b['id']
    return ''


if __name__ == '__main__':
    # openBrowser('2600696508514024b52982124919431f')
    # print(get_all_browser())
    id = get_id_by_name('123')
    print(get_window_detail(id))
    # print(openBrowser(id))
