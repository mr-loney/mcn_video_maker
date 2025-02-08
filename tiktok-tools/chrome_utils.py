import random
import time
import os
import sys
import ctypes
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By

import und as uc
import multiprocessing
import threading
import bit_api
import driver_utils
from logger import Logger
from tiktok_publish_video import TiktokVideoPublish
import psutil
import signal

log = Logger()

def get_driver(browserId):
    driverPath = ''
    debuggerAddress = ''
    try:
        retry_open_count = 0
        while retry_open_count < 300:
            res = bit_api.openBrowser(browserId)
            if res and not res['success'] and res['msg'].find('不允许多个账号同时打开') >= 0:
                print('wait')
                retry_open_count = retry_open_count + 1
                time.sleep(5)
            elif res and res['success']:
                print('open success')
                driverPath = res['data']['driver']
                debuggerAddress = res['data']['http']
                break
    except:
        log.logger.error('打开浏览器窗口失败')
        return None, None
    if len(driverPath) == 0 or len(debuggerAddress) == 0:
        log.logger.error('打开浏览器窗口失败')
        return None, None
    log.logger.info(driverPath)
    log.logger.info(debuggerAddress)

    debug_port = debuggerAddress.split(':')[-1]
    driver = get_driver_internal(int(debug_port))
    # x = random.randint(0, 500)
    # y = random.randint(10, 200)
    # driver.set_window_position(x, y)
    # driver.execute_script("window.open('about:blank','_blank');")
    # driver.switch_to.window(driver.window_handles[-1])
    # for i in range(len(driver.window_handles) - 1)[::-1]:
    #     driver.switch_to.window(driver.window_handles[i])
    #     driver.close()
    #
    # driver.switch_to.window(driver.window_handles[-1])
    return driver, browserId

def get_driver_internal(port):
    try:
        print(port)
        base_root_path = os.path.join(os.path.dirname(os.path.abspath(__file__)))
        driver = uc.Chrome(port=port,driver_executable_path=os.path.join(base_root_path, 'chrome_driver/chromedriver'))
        driver.set_page_load_timeout(90)
        return driver
    except Exception as e:
        log.logger.error('启动webdriver失败，重试')
        log.logger.exception(e)
        time.sleep(1)
    return None

def test_driver_internal():
    base_root_path = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    driver_executable_path = os.path.join(base_root_path, 'chrome_driver/chromedriver')
    uc.Chrome(port=1024, driver_executable_path=driver_executable_path)

if __name__ == "__main__":
    browser_id = bit_api.get_id_by_name('123')
    print(browser_id)
    driver,_ = get_driver(browser_id)
    if driver:
        du = driver_utils.DriverUtils(driver)
        du.open_url('https://www.baidu.com/')
        # count = 0
        # while count < 15:
        #     if du.is_element_exist('//*[@data-tt="components_InfiniteScroller_Container"]'):
        #         break
        #     count = count + 1
        # selects = du.find_elements_ext('//*[@data-tt="components_CheckboxDropdown_TUXText"]')
        # for select in selects:
        #     if select.text == "All privacy":
        #         select.click()
        # du.random_sleep()
        # items = du.find_element_ext('//*[@data-tt="components_CheckboxDropdown_TUXPopover"]').find_elements(
        #     by=By.TAG_NAME,
        #     value='span')
        # for item in items:
        #     if item.text == "Everyone" or item.text == "Friends":
        #         item.click()
        #         du.random_sleep()
        # du.random_sleep()
        # du.find_element_ext('//*[@data-tt="components_CheckboxGroup_TUXButton"]').click()
        # print(du.is_element_exist('//*[@data-tt="components_InfiniteScroller_Container"]'))
        # count = 0
        # while count < 15:
        #     if du.is_element_exist('//*[@data-tt="components_InfiniteScroller_Container"]'):
        #         break
        #     count = count + 1

        # rows = du.find_elements_ext('//*[@data-tt="Table_VirtualizedTable_Tr_23"]')
        # contents = ['Everyone', 'Friends']
        #
        # is_end = False
        # really_end = False
        # scroll_count = 0
        # post_time = []
        # while not is_end:
        #     if scroll_count > 2:
        #         rows = du.find_elements_ext('//*[@data-tt="Table_VirtualizedTable_Tr_23"]')
        #         scroll_count = 0
        #     try:
        #         for row in rows:
        #             tds = row.find_elements(by=By.TAG_NAME, value='td')
        #             print(len(tds))
        #             # index = len(tds) - 2
        #             # print(index)
        #             if len(tds) > 2:
        #                 # print(tds[index].text)
        #
        #                 image = tds[0].find_element(by=By.TAG_NAME, value='img')
        #                 if image:
        #                     url = image.get_attribute('src')
        #                     if url.find('http') >= 0:
        #                         if len(post_time) > 0 and post_time[len(post_time) - 1] == url:
        #                             is_end = True
        #                             if not is_end:
        #                                 rows = du.find_elements_ext('//*[@data-tt="Table_VirtualizedTable_Tr_23"]')
        #                         if url not in post_time:
        #                             is_end = False
        #                             print(url)
        #                             post_time.append(url)
        #                             scroll_count = scroll_count + 1
        #                             du.random_sleep()
        #                             index = len(tds) - 1
        #                             # if index > 0:
        #                             #     btns = tds[index].find_elements(by=By.TAG_NAME, value='button')
        #                             #     for btn in btns:
        #                             #         if btn.text in contents:
        #                             #             btn.click()
        #                             #             du.random_sleep()
        #                             #             items = du.find_css_elements('._TUXMenuItem-container')
        #                             #             for item in items:
        #                             #                 if item.text == 'Only me':
        #                             #                     item.click()
        #                             #                     time.sleep(2)
        #                             #                     break
        #                             driver.execute_script("arguments[0].scrollIntoView(true);", image)
        #     except:
        #         scroll_count = scroll_count + 1

    #     du.open_url('https://www.tiktok.com/tiktokstudio/content')
    #     print(du.is_element_exist('//*[@data-tt="components_InfiniteScroller_Container"]'))
    #     count = 0
    #     while count < 15:
    #         if du.is_element_exist('//*[@data-tt="components_InfiniteScroller_Container"]'):
    #             break
    #         count = count + 1
    #     rows = du.find_elements_ext('//*[@role="row"]')
    #     rows = du.find_element_ext('//*[@data-tt="Table_VirtualizedTable_TBody"]').find_elements(by=By.XPATH,
    #                                                                                       value='//*[@role="row"]')
    #     contents = ['Everyone', 'Friends']
    #     is_end = False
    #     really_end = False
    #     scroll_count = 0
    #     post_time = []
    #     while not really_end:
    #         if scroll_count > 2:
    #             rows = du.find_element_ext('//*[@data-tt="Table_VirtualizedTable_TBody"]').find_elements(by=By.XPATH,
    #                                                                                       value='//*[@role="row"]')
    #             scroll_count = 0
    #         is_error = False
    #         for row in rows:
    #             if is_error:
    #                 scroll_count = 3
    #                 is_error = True
    #                 break
    #             tds = row.find_elements(by=By.TAG_NAME, value='td')
    #             index = len(tds) - 2
    #             if index > 0:
    #                 try:
    #                     spans = tds[index].find_elements(by=By.TAG_NAME, value='span')
    #                 except:
    #                     break
    #                 for span in spans:
    #                     try:
    #                         if span.text.find(':') > 0:
    #                             if len(post_time) > 0 and post_time[len(post_time) - 1] == span.text:
    #                                 is_end = True
    #                                 if not is_end:
    #                                     rows = du.find_elements_ext('//*[@role="row"]')
    #                             if span.text not in post_time:
    #                                 is_end = False
    #                                 print(span.text)
    #                                 post_time.append(span.text)
    #                                 scroll_count = scroll_count + 1
    #                                 du.random_sleep()
    #                                 index = len(tds) - 1
    #                                 if index > 0:
    #                                     btns = tds[index].find_elements(by=By.TAG_NAME, value='button')
    #                                     for btn in btns:
    #                                         if btn.text in contents:
    #                                             btn.click()
    #                                             du.random_sleep()
    #                                             items = du.find_css_elements('._TUXMenuItem-container')
    #                                             for item in items:
    #                                                 if item.text == 'Only me':
    #                                                     item.click()
    #                                                     time.sleep(2)
    #                                                     break
    #                                 driver.execute_script("arguments[0].scrollIntoView(true);", span)
    #                     except:
    #                         scroll_count = 3
    #                         is_error = True
    #                         break

        # items = du.find_css_elements('._TUXMenuItem-container')
        # for item in items:
        #     if item.text == 'Only me':
        #         item.click()
        #         count = 0
        #         while count < 5:
        #             if du.is_element_exist_by_css('.TUXTopToast'):
        #                 print('haha')
        #                 break
        #             count = count + 1
        #             time.sleep(1)

        # inputs = du.find_css_elements('.TUXTextInputCore')
        # for i in inputs:
        #     if i.get_attribute('value').find('-') > 0:
        #         i.click()
        #         # i.send_keys('2024-06-23')
        #     print(i.get_attribute('value'))
        # print(du.find_css_element('.TUXFormField-labelRow').get_attribute('class'))

        # du.find_css_element('.add-first-btn').click()
        # btns = du.find_css_elements('.TUXButton-label')
        # for btn in btns:
        #     if btn.text == 'Next':
        #         btn.click()
        # # 搜索商品需要等待
        # print(du.find_css_element('.TUXTextInputCore-input').send_keys('1729468880023097470'))
        # du.find_css_element('.TUXTextInputCore-trailingIconWrapper').click()
        #
        # print(du.find_css_element('.product-info-cell').find_element(by=By.CSS_SELECTOR, value='.TUXRadio').click())
        #
        # # 选择完商品后需要等待
        # btns = du.find_css_element('.product-selector-modal').find_elements(by=By.CSS_SELECTOR, value='.TUXButton-label')
        # for btn in btns:
        #     if btn.text == 'Next':
        #         btn.click()
        #
        # # 输入商品名
        # print(du.find_css_element('.TUXTextInputCore-input').get_attribute('value'))
        #
        # # 点击添加需要等待
        # btns = du.find_css_elements('.TUXButton-label')
        # for btn in btns:
        #     if btn.text == 'Add':
        #         btn.click()




        # du.open_url('https://www.yalala.com/')
        # print(driver.title)
        # driver.switch_to.new_window('tab')
        # driver.switch_to.window(driver.window_handles[1])
        # video_publisher = TiktokVideoPublish(driver, du, 'account_name')
        # log.logger.info('进入视频发布页面')
        # du.open_url('https://www.tiktok.com/creator-center/upload?from=upload')
        # time.sleep(3)
        # item = driver.find_element(By.TAG_NAME, 'iframe')
        # driver.switch_to.frame(item)
        #
        # du.find_css_element('.cover-selector-image-container').click()
        # du.random_sleep()
        # du.find_css_elements('.cover-edit-tab')[1].click()
        # du.random_sleep()
        # du.input_value('//*[@id="uploadTrigger"]', '/Users/lizonghuan/Downloads/o_1gjo5pg1uf9a161f8410i6v2n8n.jpeg', is_direct=True)
        # du.random_sleep()
        # # time.sleep(3)
        # # du.click('//*[@class="css-170cvvi"]')
        #
        # print(du.find_css_elements('.cover-edit-footer')[1].find_elements(by=By.TAG_NAME, value='button')[1].click())
        # print(du.find_css_elements('.coverModeSize')[3].click())
        # du.find_css_element('.cover-edit-footer').find_elements(by=By.TAG_NAME, value='button')[1].click()
        # print(du.is_element_exist_by_css('.coverModeSize'))

        # video_publisher.upload_video('/Users/lizonghuan/Downloads/card.mp4')
        # print(du.find_css_elements('.TUXRadio')[1].click())
        # video_publisher.set_video_title('hello', '#fine#beautiful')
        # du.click('//*[@class="tiktok-select-selector"]')
        # du.random_sleep()
        # du.click('//*[@class="tiktok-select-dropdown"]/span[3]')
        # video_publisher.commit()

