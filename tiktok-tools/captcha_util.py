#!/usr/bin/python
# -*- coding:utf-8 -*-
# coding: utf-8
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common import NoSuchElementException

from AiEngine import SlidePredictor
from AiEngine import WhirlPredictor
from AiEngine import Predictor3D
from logger import Logger

log = Logger()


class CaptchaUtils:

    def __init__(self, driver):
        self.is_load_img = True
        self.driver = driver
        self.is_checking = False
        self.last_img = ''

    def is_element_exist(self, path) -> bool:
        try:
            self.driver.find_element(By.XPATH, path)
        except NoSuchElementException:
            return False
        return True

    def has_captcha(self) -> bool:
        try:
            return self.driver.find_element(By.TAG_NAME, 'body').get_attribute('class').find('captcha') >= 0
        except:
            return False

    def is_css_element_exist(self, css) -> bool:
        try:
            self.driver.find_element(By.CSS_SELECTOR, css)
        except NoSuchElementException:
            return False
        return True

    def img_loading(self):
        for i in range(15):
            if not self.is_css_element_exist('captcha_verify_message-init'):
                break
            time.sleep(1)

    def check_error(self):
        if self.is_css_element_exist('.captcha_verify_message-going'):
            self.driver.find_element(By.CSS_SELECTOR, '.secsdk_captcha_refresh').click()
            time.sleep(3)
            self.is_load_img = True

    def check_captcha(self):
        if self.has_captcha() and not self.is_checking:
            log.logger.info('start check_captcha')
            self.is_checking = True
            time.sleep(3)
            url1 = ''
            url2 = ''
            is_slide = False
            if not self.is_load_img:
                self.driver.find_element(By.CSS_SELECTOR, '.secsdk_captcha_refresh').click()
                time.sleep(3)
                self.is_load_img = True
            self.check_error()
            self.img_loading()
            if self.is_id_captcha('//*[@id="captcha_container"]'):
                if self.is_element_exist('//*[@id="captcha-verify-image"]'):
                    is_slide = True
                for i in range(5):
                    try:
                        url1 = self.driver.find_element(By.XPATH, '//*[@id="captcha_container"]/div/div[2]/img[1]').get_attribute('src')
                        self.is_load_img = True
                        break
                    except Exception as e:
                        log.logger.info('验证码暂时加载不出图片，点击刷新')
                        try:
                            self.driver.find_element(By.CSS_SELECTOR, '.secsdk_captcha_refresh').click()
                            time.sleep(10)
                        except Exception as e:
                            log.logger.info('验证码暂时加载不出图片')
                        self.is_load_img = False

                if self.is_load_img:
                    try:
                        url2 = self.driver.find_element(By.XPATH, '//*[@id="captcha_container"]/div/div[2]/img[2]').get_attribute('src')
                    except Exception as e:
                        log.logger.info('出现3d验证码')
                        # print(url1)
                        self.handle_3d_captcha(url1)
                        # tiktok_info.insert_error_info(constant.PLATFORM_TIKTOK, constant.ERROR_TYPE_REGISTER, '出现3d验证码')
                        time.sleep(5)
                        return
            elif self.is_id_captcha('//*[@id="tiktok-verify-ele"]'):
                if self.is_element_exist('//*[@id="captcha-verify-image"]'):
                    is_slide = True
                url1 = self.driver.find_element(By.XPATH, '//*[@id="tiktok-verify-ele"]/div/div[2]/img[1]').get_attribute('src')
                try:
                    url2 = self.driver.find_element(By.XPATH, '//*[@id="tiktok-verify-ele"]/div/div[2]/img[2]').get_attribute('src')
                except Exception as e:
                    log.logger.info('出现3d验证码')
                    self.handle_3d_captcha(url1)
                    time.sleep(5)
                    return
                    # tiktok_info.insert_error_info(constant.PLATFORM_TIKTOK, constant.ERROR_TYPE_REGISTER, '出现3d验证码')
            if self.last_img == url1:
                return
            if not self.is_load_img:
                return
            self.last_img = url1
            if is_slide:
                self.handle_slide_captcha(url1, url2)
            else:
                self.handle_rotation_captcha(url1, url2)
            self.is_checking = False

    def is_id_captcha(self, path):
        try:
            self.driver.find_element(By.XPATH, path)
        except NoSuchElementException:
            return False
        return True

    def handle_slide_captcha(self, url1, url2):
        distance = 0
        log.logger.info(url1)
        # data = {
        #     "captchaType": 1316,
        #     "captchaData": base64.b64encode(requests.get(url1).content).decode(),
        # }
        result = slide(url1)
        # post_str = json.dumps(data).encode(encoding='UTF8')
        # res = requests.post(OCR_URL, headers=HEADERS, data=post_str)
        # r = json.loads(res.text)
        if result:
            log.logger.info(result)
            distance = get_slide_distance(int(result['recognition'].split(',')[0]))
        slider = self.driver.find_element(By.CSS_SELECTOR, '.secsdk-captcha-drag-icon')
        actions = ActionChains(self.driver)
        actions.move_to_element(slider)
        actions.click_and_hold()
        time.sleep(1)
        for index in get_track(distance):
            time.sleep(0.25)
            actions.move_by_offset(index, 0)
        time.sleep(1)
        actions.release()
        actions.perform()
        time.sleep(3)

    def handle_rotation_captcha(self, url1, url2):
        distance = 0
        log.logger.info(url1)
        log.logger.info(url2)
        result = whirl(url1, url2)
        if result:
            distance = get_rotation_distance(int(result['recognition']))
        slider = self.driver.find_element(By.CSS_SELECTOR, '.secsdk-captcha-drag-icon')
        actions = ActionChains(self.driver)
        actions.move_to_element(slider)
        actions.click_and_hold()
        time.sleep(1)
        for index in get_track(distance):
            time.sleep(0.25)
            actions.move_by_offset(index, 0)
        time.sleep(1)
        actions.release()
        actions.perform()
        time.sleep(3)

    def handle_3d_captcha(self, url1):
        log.logger.info(url1)
        result = third_3d(url1)
        time.sleep(3)
        if result:
            log.logger.info(result['recognition'])
            img = self.driver.find_element(By.XPATH, '//*[@id="captcha_container"]/div/div[2]/img[1]')
            width = img.size['width']
            height = img.size['height']
            log.logger.info(f"width:{width},height:{height}")
            left1 = int(result['recognition'][0][0]) + ((int(result['recognition'][0][2]) - int(result['recognition'][0][0])) / 2)
            top1 = int(result['recognition'][0][1]) + ((int(result['recognition'][0][3]) - int(result['recognition'][0][1])) / 2)
            actions = ActionChains(self.driver)
            actions.move_to_element(img)
            actions.move_by_offset(-int(width/2), -int(height/2))
            RenderedWIDTHALL = 340
            IntrinsicWIDTHALL = 552
            PaddingWidth = 8
            real_left1 = round((left1 * RenderedWIDTHALL / IntrinsicWIDTHALL), 4)
            real_top1 = round((top1 * RenderedWIDTHALL / IntrinsicWIDTHALL) , 4)
            log.logger.info(f"real_left1:{real_left1}")
            log.logger.info(f"real_top1:{real_top1}")
            actions.move_by_offset(real_left1, real_top1)
            actions.click()
            actions.perform()
            time.sleep(1.5)

            left2 = int(result['recognition'][1][0]) + ((int(result['recognition'][1][2]) - int(result['recognition'][1][0])) / 2)
            top2 = int(result['recognition'][1][1]) + ((int(result['recognition'][1][3]) - int(result['recognition'][1][1])) / 2)
            actions.move_to_element(img)
            actions.move_by_offset(-int(width / 2), -int(height / 2))
            RenderedWIDTHALL = 340
            IntrinsicWIDTHALL = 552
            PaddingWidth = 8
            real_left2 = round((left2 * RenderedWIDTHALL / IntrinsicWIDTHALL), 4)
            real_top2 = round((top2 * RenderedWIDTHALL / IntrinsicWIDTHALL), 4)
            log.logger.info(f"real_left2:{real_left2}")
            log.logger.info(f"real_top2:{real_top2}")
            actions.move_by_offset(real_left2, real_top2)
            actions.click()
            actions.perform()
            time.sleep(2)
            self.driver.find_element(By.XPATH, '//*[@id="captcha_container"]/div/div[3]/div[2]').click()
            time.sleep(3)
        self.is_checking = False


def get_slide_distance(recognition):
    log.logger.info(f'需要移动真实距离：${recognition}')
    RenderedWIDTHALL = 340
    IntrinsicWIDTHALL = 552
    PaddingWidth = 8
    distance = round((recognition * RenderedWIDTHALL / IntrinsicWIDTHALL), 4)
    distance = round(distance - (RenderedWIDTHALL / IntrinsicWIDTHALL * PaddingWidth), 4)
    log.logger.info(f'需要移动相对距离：${distance}')
    return distance * 2.05


def get_rotation_distance(recognition):
    deg_all = 178.378
    width_all = 271.014
    return round(abs(recognition * 1) * width_all / deg_all, 4)


def get_track(distance):
    track = []
    d = 2
    n = 0
    s = 0
    S = 0
    while S < distance:
        s = 1 + n
        n = n + d
        S += s
        track.append(s)
    log.logger.info(track)
    diff = (S - distance)
    last = int(track[len(track) - 1] - diff)
    track.remove(track[len(track) - 1])
    track.append(last)
    return track


def slide(path):
    model = SlidePredictor()
    input_dict = {
        "url1": path
    }
    try:
        code, msg, data = model.process(input_dict)
        if code == 200:
            label_info = data["label_info"]
            box = label_info["bbox"]
            x = box[0]
            y = box[1]
            data = {
                "recognition": str(round(x)) + "," + str(round(y))
        }
    finally:
        print('')
    return data


def whirl(path_main, path_sub):
    model = WhirlPredictor()
    input_dict = {
        "img1": path_main,  # 大图
        "img2": path_sub  # 子图
    }
    try:
        code, msg, data = model.process(input_dict)
        if code == 200:
            data = {
                "recognition": data["label_info"]["angle"]
            }
    finally:
        print('')
    return data


def third_3d(path):
    model = Predictor3D()
    input_dict = {
        "url1": path
    }
    try:
        code, msg, data = model.process(input_dict)
        if code == 200:
            label_info = data["label_info"]
            box = label_info["bboxes"]
            data = {
                "recognition": box
            }
    finally:
        print('')
    return data