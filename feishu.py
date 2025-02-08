import time
import requests
import base64
import json
import string
import random
import re
import time
from datetime import datetime, timedelta
from loguru import logger

token = ''
task_table_id = 'tbly8CLLObzuvpAQ'
app_token = 'ZLDDbpCa0aSXagsDzgpcGsVFnzd'

class FeiShuDoc:
    def get_access_token(self):
        global token
        global expire_time
        timestamp_seconds = int(time.time())
        if len(token) != 0 and timestamp_seconds < expire_time:
            return token
        headers = {
            'Content-Type': "application/json; charset=utf-8"
        }
        values = {
            "app_id": "cli_a63bc2b4df3c1013",
            "app_secret": "iKLHUAeFkN8DnYs8VJWMFed5id8dvYDK"
        }
        data = json.dumps(values).encode(encoding='UTF8')
        try:
            res = requests.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal', headers=headers, data=data).json()
            # logger.info(res)
            if res is not None or res['code'] == 0:
                token = res['tenant_access_token']
                expire_time = int(time.time()) + res['expire'] - 30
                return token
        except Exception:
            logger.info('获取feishu token失败')
        return ''

    def get_task_status(self, taskid_list):
        if len(taskid_list) == 0:
            return []

        access_token = self.get_access_token()
        if len(access_token) == 0:
            return []
        header = {"content-type": "application/json",
                "Authorization": f"Bearer {access_token}"}

        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{task_table_id}/records/batch_get"
        values = {
            "record_ids": taskid_list,
            "user_id_type": "open_id"
        }

        try:
            res = requests.post(url, headers=header, data=json.dumps(values)).json()
            status_list = []

            for task_id in taskid_list:
                status_found = False  # 用于标记是否找到对应的状态
                for record in res['data']['records']:
                    if task_id == record['record_id']:
                        if record['fields']['状态'] == "已完成":
                            if record['fields']['是否生成数字人'] == "是":
                                if record['fields']['数字人状态'] == "已完成":
                                    status_list.append("已完成,数字人成功")
                                elif record['fields']['数字人状态'] == "已失败":
                                    status_list.append("已完成,数字人失败")
                                else:
                                    status_list.append("已完成,数字人执行中")
                            else:
                                status_list.append(record['fields']['状态'])
                        elif record['fields']['状态'] == "已失败":
                            status_list.append(record['fields']['状态'])
                        else:
                            status_list.append(record['fields']['状态'])
                        status_found = True
                        break  # 跳出 records 的循环

                if not status_found:
                    # 如果未找到匹配状态，可以选择添加默认值，例如 "未知"
                    status_list.append("未知")

            return status_list
        except Exception:
            return []
    
    def repostTask(self, recordid, status, create_human_status):
        access_token = self.get_access_token()

        if len(access_token) == 0:
            return []
        
        header = {"content-type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {access_token}"}
        
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{task_table_id}/records/{recordid}"

        if status == True:
            values = {
                "fields":{
                    "状态": "已准备"
                }
            }
        elif create_human_status == True:
            values = {
                "fields":{
                    "数字人状态": "已准备"
                }
            }
        else:
            values = {}

        try:
            res = requests.put(url, headers=header, data=json.dumps(values))
            logger.info("重置任务成功:" + res.text)
        except:
            logger.info("添加任务失败")
        
        return recordid

    def appendTask(self, data):
        access_token = self.get_access_token()

        if len(access_token) == 0:
            return []
        
        header = {"content-type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {access_token}"}
        
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{task_table_id}/records"

        if data["is_create_human"] == True:
            title = "生视频任务(带数字人)"
            templateName = "splice_digital_human"
            tasktype = "模版任务"
        else:
            title = "生视频任务"
            templateName = "splice"
            tasktype = "模版任务"

        if data["widget"] == "GenTemplateImage":
            title = "多图任务"
            templateName = "normal"
            tasktype = "模版任务"
        
        values = {
            "fields":{
                "任务备注": title,
                "任务编码": data["ftp_folder_name"],
                "账号id": data["social_account"],
                "config": data["config"],
                "状态": "已准备",
                "任务类型": tasktype,
                "虚拟账号": self.boolean_to_chinese(data["use_anonymous"]),
                "添加新模板": self.boolean_to_chinese(data["is_new_template"]),
                "矩阵名": data["matrix_template"],
                "widget": data["widget"],
                "时间": self.convert_time_string_to_list(data["publish_time"]),
                "音乐名": data["music_name"],
                "音乐序列号": data["music_index"],
                "音乐音量": data["music_volume"],
                "原声音量": data["original_volume"],
                "橱窗商品": data["window_product"],
                "发布到tiktok的标题": data["tiktok_title"],
                "发布到tiktok的标题tag": data["tiktok_tags"],
                "发布到tiktok的标题@": data["tiktok_at"],
                "首条评论": data["first_comment"],
                "重发高播放量视频": self.boolean_to_chinese(data["repost_high_views"]),
                "重发达到n播放量视频": self.string_to_number(data["repost_views_threshold"]),
                "是否生成数字人": self.boolean_to_chinese(data["is_create_human"]),
                "数字人状态": "未运行",
                "模版": templateName
            }
        }

        try:
            res = requests.post(url, headers=header, data=json.dumps(values))
            logger.info("添加任务成功:" + res.text)
            return res.json()['data']['record']['record_id']
        except:
            logger.info("添加任务失败")
            return -1

    def string_to_number(self, value, default=0):
        """
        将字符串转换为数字，如果是空字符串或转换失败，返回默认值。

        :param value: 字符串
        :param default: 转换失败时返回的默认值（默认为 0）
        :return: 转换后的数字
        """
        try:
            # 如果是空字符串，直接返回默认值
            if value.strip() == "":
                return default
            # 尝试转换为浮点数或整数
            return float(value) if '.' in value else int(value)
        except ValueError:
            # 转换失败返回默认值
            return default
    
    def boolean_to_chinese(self, value):
        """
        将布尔值转换为中文 "是" 或 "否"。
        
        :param value: 布尔值 (True 或 False)
        :return: "是" 或 "否"
        """
        return "是" if value else "否"

    def convert_time_string_to_list(self, time_string):
        """
        将逗号分隔的时间字符串转换为数组。

        :param time_string: 时间字符串，如 "4:00,10:00,18:00"
        :return: 时间数组，如 ["4:00", "10:00", "18:00"]
        """
        if not time_string:
            return []
        return [time.strip() for time in time_string.split(",")]

    def get_key(self, mkey):
        if mkey == "":
            return False
        
        access_token = self.get_access_token()
        if len(access_token) == 0:
            return False
        header = {"content-type": "application/json",
                "Authorization": f"Bearer {access_token}"}

        this_table_id = "tblLvH7KbYCWRVih"
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{this_table_id}/records/search"
        
        values = {
            "sort":[{
                "field_name":"创建时间",
                "desc": True
            }],
            "field_names":[
                "key",
            ],
            "filter":{
                "conjunction":"and",
                "conditions":[
                    {
                        "field_name":"key",
                        "operator":"contains",
                        "value":[
                            mkey
                        ]
                    },
                ]
            }
        }

        try:
            res = requests.post(url, headers=header, data=json.dumps(values)).json()
            if res["msg"] == "success":
                if len(res["data"]["items"]) > 0:
                    return True
                else:
                    return False
            else:
                return False
        except Exception:
            return False