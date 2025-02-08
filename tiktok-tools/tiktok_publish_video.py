# -*- coding:utf-8 -*-
# coding: utf-8
import os
import random
import time
from time import sleep
import pyperclip as cb

from selenium.webdriver import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

from logger import Logger

log = Logger()


class TiktokVideoPublish:

    def __init__(self, driver, driver_utils, outlook_account):
        self.driver = driver
        self.outlook_account = outlook_account
        self.driver_utils = driver_utils
        self.upload_retry = False

    def publish_video(self, video_path, title, topic) -> bool:
        if not self.upload_video(video_path):
            log.logger.error(f'{self.outlook_account}上传视频失败')
            return False
        else:
            log.logger.info(f'{self.outlook_account}上传视频成功')
        if not self.analysis_video(video_path):
            log.logger.error(f'{self.outlook_account}解析视频失败')
            return False
        # switch_list = self.driver_utils.find_elements_ext('(//*[@role="switch"])')
        # if len(switch_list) > 1:
        #     switch_list[1].click()
        # elif len(switch_list) == 1:
        #     switch_list[0].click()
        self.set_video_title(title, topic)
        self.driver_utils.captcha_util.check_captcha()
        # self.copyright_check(video_path)
        self.driver_utils.captcha_util.check_captcha()
        self.commit()
        return True

    def upload_video(self, video_path) -> bool:
        # self.discard_video()
        input1 = '//*[@id="root"]/div/div/div/div[1]/div/div/div/input'

        for input1 in self.driver.find_elements(By.TAG_NAME, 'input'):
            accept = input1.get_attribute("accept")
            if accept and len(accept) > 0:
                #上传图片
                input1.send_keys(video_path)
        
        log.logger.info(f'开始上传视频：{video_path}')
        time.sleep(3)
        upload_count = 0
        while not self.driver_utils.is_element_exist_by_css('.info-progress-num'):
            if upload_count > 100:
                return False
            log.logger.info(f'等待上传视频：{video_path}')
            upload_count = upload_count + 1
            sleep(1)
        upload_count = 0
        retry_count = 0
        while self.driver_utils.is_element_exist_by_css('.info-progress-num'):
            if upload_count > 600:
                return False
            if self.driver_utils.find_css_element('.info-progress-num').text == '100%':
                break
            sleep(2)
            upload_count = upload_count + 1
            log.logger.info(f'正在上传视频：{video_path}')
            if retry_count > 2:
                return False
            elif self.check_upload_retry():
                retry_count = retry_count + 1

        upload_count = 0
        while not self.driver_utils.is_element_exist('(//*[@data-contents="true"]/div/div/span/span)'):
            if upload_count > 100:
                return False
            sleep(2)
            upload_count = upload_count + 1
            log.logger.info(f'正在解析视频：{video_path}')
        return True

    def analysis_video(self, video_path) -> bool:
        log.logger.info('上传完毕，开始解析')
        upload_count = 0
        while not self.driver_utils.is_element_exist('(//*[@data-contents="true"]/div/div/span/span)'):
            if upload_count > 40:
                return False
            sleep(1)
            upload_count = upload_count + 1
        log.logger.info('解析完毕')
        return True

    def set_at(self, at_str, actions):
        for i in range(0, len(at_str)):
            sleep(0.5)
            actions.send_keys(at_str[i])
            actions.perform()
        sleep(3)
        actions.send_keys(Keys.ENTER)
        actions.perform()
        sleep(1)

    # def set_topic(self, topics, actions):
    #     sleep(1)
    #     actions.send_keys(' ')
    #     actions.perform()
    #     sleep(1)
    #     for t in topics.split('#'):
    #         if len(t) == 0:
    #             continue
    #         topic = f'#{t}'.strip()
    #         cb.copy(topic)
    #         actions.key_down(Keys.COMMAND).perform()
    #         actions.send_keys('v').perform()
    #         actions.key_up(Keys.COMMAND).perform()
    #         sleep(3)
    #         actions.send_keys(Keys.ENTER).perform()
    #     sleep(1)
    
    def set_topic(self, topics, actions):
        """
        不使用复制粘贴，直接通过 actions.send_keys() 将文本逐个输入
        """
        from selenium.webdriver.common.keys import Keys
        from time import sleep

        sleep(1)
        # 先在末尾加个空格，触发输入
        actions.send_keys(' ')
        actions.perform()
        sleep(1)

        # 将话题按 '#' 拆分
        for t in topics.split('#'):
            if len(t.strip()) == 0:
                continue
            # 拼接 # 前缀
            topic = f'#{t.strip()}'
            # 直接 send_keys
            # 比如先输入 topic
            actions.send_keys(topic)
            actions.perform()
            sleep(2)
            # 回车确认
            actions.send_keys(Keys.ENTER)
            actions.perform()
            sleep(1)

    def set_video_title(self, title, topics):
        if len(topics) == 0:
            log.logger.info('没有设置视频话题')
            return
        content_item = self.driver_utils.find_element_ext('(//*[@data-contents="true"]/div/div/span/span)')
        if not content_item:
            return
        back = len(content_item.text)
        actions = ActionChains(self.driver)
        actions.move_to_element(content_item)
        actions.click()
        actions.perform()
        self.driver_utils.random_sleep()
        actions.send_keys(Keys.END)
        actions.perform()
        self.driver_utils.random_sleep()
        for b in range(back):
            actions.send_keys(Keys.BACKSPACE)
            actions.perform()
        at_index = topics.find('@')
        if at_index > 0:
            at_str = topics[at_index: len(topics)]
            self.set_at(at_str, actions)
            topics = topics[0: at_index]
        actions.send_keys(' ')
        actions.send_keys(title)
        actions.perform()
        self.set_topic(topics, actions)

    def add_product(self, product_id=''):
        self.driver_utils.find_css_element('.add-first-btn').click()
        self.driver_utils.random_sleep()
        btns = self.driver_utils.find_css_elements('.TUXButton-label')
        for btn in btns:
            if btn.text == 'Next':
                btn.click()
                break
        self.driver_utils.random_sleep()
        # 搜索商品需要等待
        self.driver_utils.find_css_element('.TUXTextInputCore-input').send_keys(product_id)
        self.driver_utils.find_css_element('.TUXTextInputCore-trailingIconWrapper').click()
        wait_time = 0
        while wait_time < 10:
            if self.driver_utils.is_element_exist_by_css('.product-info-cell'):
                break
            sleep(2)
            wait_time = wait_time + 1
        self.driver_utils.find_css_element('.product-info-cell').find_element(by=By.CSS_SELECTOR,
                                                                              value='.TUXRadio').click()
        self.driver_utils.random_sleep()
        # 选择完商品后需要等待
        btns = self.driver_utils.find_css_element('.product-selector-modal').find_elements(by=By.CSS_SELECTOR,
                                                                            value='.TUXButton-label')
        for btn in btns:
            if btn.text == 'Next':
                btn.click()
                sleep(5)
                break
        # while wait_time < 10:
        #     if self.driver_utils.is_element_exist_by_css('.TUXTextInputCore-input'):
        #         break
        #     sleep(2)
        #     wait_time = wait_time + 1
        # 输入商品名
        # print(self.driver_utils.find_css_element('.TUXTextInputCore-input').get_attribute('value'))

        # 点击添加需要等待
        btns = self.driver_utils.find_css_elements('.TUXButton-label')
        for btn in btns:
            if btn.text == 'Add':
                btn.click()
                sleep(5)
                break

    def is_publish(self):
        return self.driver_utils.is_element_exist_by_css(
            '.tiktok-modal__modal-wrapper') or self.driver_utils.is_element_exist_by_css('.modal-mask-container')

    def commit(self):
        if self.driver_utils.captcha_util.has_captcha():
            time.sleep(60)
        try:
            # 尝试查找第一个按钮
            button1_xpath = '//*[@class="TUXButton TUXButton--default TUXButton--large TUXButton--primary"]'
            button2_xpath = '//*[@id="root"]/div/div/div[2]/div[2]/div/div/div/div[4]/div/button[1]'

            # 检查第一个按钮是否存在
            from selenium.webdriver.common.by import By
            elements = self.driver.find_elements(By.XPATH, button1_xpath)

            if not elements:  # 如果没有找到第一个按钮
                # 如果第一个按钮没有找到，则点击第二个按钮
                self.driver_utils.click(button2_xpath)
            else:
                # 如果找到了第一个按钮，则点击第一个按钮
                self.driver_utils.click(button1_xpath)
            # self.driver_utils.click('(//*[@class="TUXButton TUXButton--default TUXButton--large TUXButton--primary"])')
        except:
            sleep(5)
            button1_xpath = '//*[@class="TUXButton TUXButton--default TUXButton--large TUXButton--primary"]'
            button2_xpath = '//*[@id="root"]/div/div/div[2]/div[2]/div/div/div/div[4]/div/button[1]'

            # 检查第一个按钮是否存在
            from selenium.webdriver.common.by import By
            elements = self.driver.find_elements(By.XPATH, button1_xpath)

            if not elements:  # 如果没有找到第一个按钮
                # 如果第一个按钮没有找到，则点击第二个按钮
                self.driver_utils.click(button2_xpath)
            else:
                # 如果找到了第一个按钮，则点击第一个按钮
                self.driver_utils.click(button1_xpath)
            # self.driver_utils.click('(//*[@class="TUXButton TUXButton--default TUXButton--large TUXButton--primary"])')
        sleep(5)

    def check_upload_retry(self):
        if self.driver_utils.is_element_exist_by_css('.common-modal'):
            btns = self.driver_utils.find_css_element('.common-modal').find_elements(by=By.TAG_NAME, value='button')
            for btn in btns:
                print(btn.text)
                if btn.text == 'Retry':
                    btn.click()
                    return True
        return False

    def discard_video(self):
        if self.driver_utils.is_element_exist_by_css('.local-draft-card'):
            btns = self.driver_utils.find_css_element('.local-draft-card').find_elements(by=By.TAG_NAME, value='button')
            for btn in btns:
                if btn.text == 'Discard':
                    btn.click()
                    self.driver_utils.random_sleep()
            self.driver_utils.random_sleep()
            btns = self.driver_utils.find_css_element('.common-modal-confirm-modal').find_elements(by=By.TAG_NAME, value='button')
            for btn in btns:
                if btn.text == 'Discard':
                    btn.click()
                    self.driver_utils.random_sleep()

    def apply_scheduled(self):
        self.driver_utils.find_css_elements('.TUXRadio')[1].click()
        self.driver_utils.random_sleep()
        if self.driver_utils.is_element_exist_by_css('.common-modal-confirm-modal'):
            btns = self.driver_utils.find_css_element('.common-modal-confirm-modal').find_elements(by=By.TAG_NAME, value='button')
            for btn in btns:
                if btn.text == 'Allow':
                    btn.click()
                    self.driver_utils.random_sleep()
                    break


def get_local_video() -> str:
    video_root_path = f'{os.getcwd()}/video/'
    video_list = []
    video_dirs = []
    for root, dirs, files in os.walk(video_root_path):
        for video_dir in dirs:
            video_dirs.append(video_dir)
    # log.logger.info(video_dirs)
    for video_dir in video_dirs:
        video_dir_path = video_root_path + video_dir + '/'
        for root, dirs, files in os.walk(video_dir_path):
            # print(len(files))
            if len(files) == 0:
                os.removedirs(video_dir_path)
            else:
                for file_name in files:
                    video_file_path = video_dir_path + file_name
                    video_size = get_file_size(video_file_path)
                    if (video_size < 0.3 or video_size > 50) and file_name.lower().find('mp4') < 0:
                        os.remove(video_file_path)
                    else:
                        video_list.append(video_file_path)
        if len(video_list) == 0:
            return ''
        return video_list[random.randint(0, len(video_list) - 1)]
    return ''


def get_file_size(filePath):
    fsize = os.path.getsize(filePath)
    fsize = fsize / float(1024 * 1024)
    return round(fsize, 2)


if __name__ == "__main__":
    print('1')