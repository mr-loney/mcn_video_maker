import argparse
import os
import time
import requests
import re
import bit_api
import chrome_utils
from logger import Logger
import driver_utils
from tiktok_publish_video import TiktokVideoPublish
from selenium.webdriver.common.by import By
from logger import Logger

def publish_video(video_dir, video_name, browser_id, product_id=None, is_pre="否", log=None):
    print('start publish_video')
    log = Logger()
    video_dir_path = video_dir + '/'
    print(video_dir_path)
    for root, dirs, files in os.walk(video_dir_path):
        for file_name in files:
            # print(file_name)
            if file_name.lower().find(video_name) >= 0:
                video_file_path = video_dir_path + file_name
                with open(f'{video_dir_path}new.txt', "r") as file:
                    content = file.read()
                    title = content[0: content.find('#')]
                    part_suffix = ""
                    match = re.search(r'result_(\d+)\.mp4$', video_name, flags=re.IGNORECASE)
                    if match:
                        part_num = match.group(1)
                        part_suffix = f"Part_{part_num}: "
                    title = part_suffix + title
                    topics = content[content.find('#'): len(content)]
                    print(title)
                    print(topics)
                if len(title) > 0 and len(topics) > 0:
                    print(video_file_path)
                    driver, _ = chrome_utils.get_driver(browser_id)
                    time.sleep(2)
                    if driver:
                        du = driver_utils.DriverUtils(driver)
                        driver.switch_to.new_window('tab')
                        driver.switch_to.window(driver.window_handles[1])
                        video_publisher = TiktokVideoPublish(driver, du, 'account_name')
                        log.logger.info('进入视频发布页面')
                        du.open_url('https://www.tiktok.com/tiktokstudio/upload?from=upload')
                        time.sleep(1)
                        try:
                            item = driver.find_element(By.TAG_NAME, 'iframe')
                            driver.switch_to.frame(item)
                        except:
                            pass
                        # if video_publisher.upload_video(video_file_path):
                        #     log.logger.info('上传视频成功')
                        # else:
                        #     log.logger.info(f'上传视频失败{video_file_path}')
                        # video_publisher.set_video_title(title, topics)
                        from concurrent.futures import ThreadPoolExecutor, as_completed

                        def do_upload():
                            if not video_publisher.upload_video(video_file_path):
                                raise RuntimeError(f"上传视频失败: {video_file_path}")
                            log.logger.info("上传视频成功")

                        def do_set_title():
                            video_publisher.set_video_title(title, topics)
                            log.logger.info("标题设置完成")

                        with ThreadPoolExecutor(max_workers=2) as executor:
                            futures = []
                            futures.append(executor.submit(do_upload))
                            futures.append(executor.submit(do_set_title))

                            # 等待俩任务都完成
                            for future in as_completed(futures):
                                try:
                                    future.result()  # 任意抛出异常都会在这里出现
                                except Exception as e:
                                    log.logger.info(f"并行任务出错: {e}")
                                    # 如果出错，可在此选择 return 或后续处理
                                    # return

                        log.logger.info("上传视频 & 标题填写已完成(并行)")

                        du.random_sleep()
                        if product_id is not None and len(product_id) > 0:
                            try:
                                video_publisher.add_product(product_id=product_id)
                                du.random_sleep()
                            except:
                                log.logger.info(f'添加商品失败：{product_id}')

                        # 预约发布
                        if is_pre == "是":
                            video_publisher.apply_scheduled()
                        video_publisher.commit()
                        time.sleep(3)
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                        time.sleep(2)
                        bit_api.closeBrowser(browser_id)


def apply_scheduled(du):
    if du.is_element_exist_by_css('.common-modal-confirm-modal'):
        btns = du.find_css_element('.common-modal-confirm-modal').find_elements(by=By.TAG_NAME, value='button')
        for btn in btns:
            if btn.text == 'Allow':
                btn.click()


def hide_video(browser_id):
    driver, _ = chrome_utils.get_driver(browser_id)
    time.sleep(3)
    if driver:
        du = driver_utils.DriverUtils(driver)
        driver.maximize_window()
        du.random_sleep()
        driver.switch_to.new_window('tab')
        driver.switch_to.window(driver.window_handles[1])
        du.random_sleep()
        du.open_url('https://www.tiktok.com/tiktokstudio/content')
        count = 0
        while count < 15:
            if du.is_element_exist('//*[@data-tt="components_InfiniteScroller_Container"]'):
                break
            count = count + 1
        selects = du.find_elements_ext('//*[@data-tt="components_CheckboxDropdown_TUXText"]')
        for select in selects:
            if select.text == "All privacy":
                select.click()
        du.random_sleep()
        items = du.find_element_ext('//*[@data-tt="components_CheckboxDropdown_TUXPopover"]').find_elements(by=By.TAG_NAME,
                                                                                                            value='span')
        for item in items:
            if item.text == "Everyone" or item.text == "Friends":
                item.click()
                du.random_sleep()
        du.random_sleep()
        du.find_element_ext('//*[@data-tt="components_CheckboxGroup_TUXButton"]').click()
        print(du.is_element_exist('//*[@data-tt="components_InfiniteScroller_Container"]'))
        count = 0
        while count < 15:
            if du.is_element_exist('//*[@data-tt="components_InfiniteScroller_Container"]'):
                break
            count = count + 1
        rows = du.find_elements_ext('//*[@data-tt="Table_VirtualizedTable_Tr_23"]')
        contents = ['Everyone', 'Friends']

        is_end = False
        scroll_count = 0
        image_urls = []
        end_count = 0
        while not is_end and end_count < 2:
            if scroll_count > 2:
                rows = du.find_elements_ext('//*[@data-tt="Table_VirtualizedTable_Tr_23"]')
                scroll_count = 0
            try:
                for row in rows:
                    tds = row.find_elements(by=By.TAG_NAME, value='td')
                    # print(len(tds))
                    if len(tds) > 3:
                        image = tds[0].find_element(by=By.TAG_NAME, value='img')
                        if image:
                            url = image.get_attribute('src')
                            if url.find('http') >= 0:
                                if len(image_urls) > 0 and image_urls[len(image_urls) - 1] == url:
                                    is_end = True
                                    end_count = end_count + 1
                                    if not is_end:
                                        rows = du.find_elements_ext('//*[@data-tt="Table_VirtualizedTable_Tr_23"]')
                                if url not in image_urls:
                                    is_end = False
                                    end_count = 0
                                    # print(url)
                                    image_urls.append(url)
                                    scroll_count = scroll_count + 1
                                    du.random_sleep()
                                    index = len(tds) - 1
                                    if index > 0:
                                        btns = tds[index].find_elements(by=By.TAG_NAME, value='button')
                                        for btn in btns:
                                            if btn.text in contents:
                                                btn.click()
                                                du.random_sleep()
                                                items = du.find_css_elements('._TUXMenuItem-container')
                                                for item in items:
                                                    if item.text == 'Only me':
                                                        item.click()
                                                        time.sleep(2)
                                                        break
                                    driver.execute_script("arguments[0].scrollIntoView(true);", image)
            except:
                scroll_count = scroll_count + 1
        time.sleep(3)
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        time.sleep(2)
        bit_api.closeBrowser(browser_id)


def set_private(du):
    time.sleep(3)
    du.click('//*[@data-e2e="video-setting"]')
    du.random_sleep()
    du.click('//*[@data-e2e="video-privacy-settings"]')
    du.random_sleep()
    du.click('//*[@data-e2e="video-setting-choose"]')
    du.random_sleep()
    du.find_elements_ext('//*[@data-e2e="video-watch-list"]')[2].click()
    du.random_sleep()
    du.click('//*[@data-e2e="video-setting-down"]')
    du.random_sleep()
    if du.find_element_ext('//*[@data-e2e="arrow-right"]').get_attribute('disabled') is None:
        du.click('//*[@data-e2e="arrow-right"]')
    time.sleep(3)

def main():
    """
    把命令行解析、检查参数、调度逻辑都放这里
    """
    log = Logger()

    parser = argparse.ArgumentParser()
    parser.add_argument('--env_id', dest='env_id')
    parser.add_argument('--video_root_path', dest='video_root_path')
    parser.add_argument('--video_name', dest='video_name')
    parser.add_argument('--node_ip', dest='node_ip')
    parser.add_argument('--product_id', dest='product_id')
    parser.add_argument('--oper_type', dest='oper_type')
    parser.add_argument('--is_pre', dest='is_pre')
    args = parser.parse_args()

    env_id = args.env_id
    video_root_path = args.video_root_path
    video_name = args.video_name
    node_ip = args.node_ip
    product_id = args.product_id
    oper_type = args.oper_type
    is_pre = args.is_pre

    print(f'env_id:{env_id}')
    print(f'video_root_path:{video_root_path}')
    print(f'video_name:{video_name}')
    print(f'product_id:{product_id}')
    print(f'oper_type:{oper_type}')
    print(f'is_pre:{is_pre}')

    # 参数校验
    if env_id is None or (oper_type is None and (video_root_path is None or video_name is None)):
        print('参数错误')
        exit(1)

    # 找到浏览器 ID
    browser_id = bit_api.get_id_by_name(env_id)
    if len(browser_id) == 0:
        print(f'找不到浏览器帐号环境:{env_id}')
        exit(1)

    # 根据 oper_type 调用不同函数
    if oper_type is None:
        # 默认行为 => 发布视频
        try:
            publish_video(
                video_dir=video_root_path,
                video_name=video_name,
                browser_id=browser_id,
                product_id=product_id,
                is_pre=is_pre,
                log=log
            )
        except Exception as e:
            print(e)
            exit(1)
    elif oper_type == 'hide_video':
        try:
            hide_video(browser_id)
        except Exception as e:
            print(e)
            exit(1)

if __name__ == "__main__":
    # 只有在命令行执行 start.py 时才会执行 main()
    main()

# if __name__ == "__main__":
#     log = Logger()
#     parser = argparse.ArgumentParser()
#     parser.add_argument('--env_id', dest='env_id')
#     parser.add_argument('--video_root_path', dest='video_root_path')
#     parser.add_argument('--video_name', dest='video_name')
#     parser.add_argument('--node_ip', dest='node_ip')
#     parser.add_argument('--product_id', dest='product_id')
#     parser.add_argument('--oper_type', dest='oper_type')
#     parser.add_argument('--is_pre', dest='is_pre')
#     args = parser.parse_args()
#     env_id = args.env_id
#     video_root_path = args.video_root_path
#     video_name = args.video_name
#     node_ip = args.node_ip
#     product_id = args.product_id
#     oper_type = args.oper_type
#     is_pre = args.is_pre
#     print(f'env_id:{env_id}')
#     print(f'video_root_path:{video_root_path}')
#     print(f'video_name:{video_name}')
#     print(f'product_id:{product_id}')
#     print(f'oper_type:{oper_type}')
#     print(f'is_pre:{is_pre}')
#     if env_id is None or (oper_type is None and (video_root_path is None or video_name is None)) :
#         print('参数错误')
#         exit(1)
#     browser_id = bit_api.get_id_by_name(env_id)
#     if len(browser_id) == 0:
#         print(f'找不到浏览器帐号环境:{env_id}')
#         exit(1)
#     check_count = 0
#     proxy_success = False
#     time.sleep(3)
#     current_ip = ''
    
#     if oper_type is None:
#         try:
#             publish_video(video_root_path, video_name, is_pre)
#         except:
#             exit(1)
#     elif oper_type == 'hide_video':
#         try:
#             hide_video()
#         except:
#             exit(1)



