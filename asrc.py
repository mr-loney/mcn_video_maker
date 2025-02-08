import time, requests, re, json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

base_url = 'https://openspeech.bytedance.com/api/v1/vc'
appid = "7923109653"
access_token = "GCbvq6WYTaSI3F9p3qpjUUprtjnDNSJ3"

def log_time(func):
    def wrapper(*args, **kw):
        begin_time = time.time()
        func(*args, **kw)
        print('total cost time = {time}'.format(time=time.time() - begin_time))
    return wrapper

def sendASR(file_url, language, words_per_line, file_name, callback, m_use_itn='False', m_use_capitalize='False', m_use_punc=False, org_text=""):
    try:
        response = requests.post(
                    '{base_url}/submit'.format(base_url=base_url),
                    params=dict(
                        appid=appid,
                        language=language,
                        use_itn=m_use_itn,
                        use_capitalize=m_use_capitalize,
                        use_punc=m_use_punc,
                        max_lines=1,
                        words_per_line=words_per_line
                    ),
                    json={
                        'url': file_url,
                    },
                    headers={
                        'content-type': 'application/json',
                        'Authorization': 'Bearer; {}'.format(access_token)
                    },timeout=60, verify=False
                )
        print('submit response = {}'.format(response.text))
        
        if "message" in response.json():
            assert(response.status_code == 200)
            assert(response.json()['message'] == 'Success')

            job_id = response.json()['id']
            response = requests.get(
                    '{base_url}/query'.format(base_url=base_url),
                    params=dict(
                        appid=appid,
                        id=job_id,
                    ),
                    headers={
                    'Authorization': 'Bearer; {}'.format(access_token)
                    },timeout=60, verify=False
            )

            callback(file_name, response.text)
            assert(response.status_code == 200)
        else:
            print("歌词转换出错,重试!")
            sendASR(file_url, language, words_per_line, file_name, callback, m_use_itn, m_use_capitalize)
    except Exception as ex:
        print("歌词转换出错,重试! " + str(ex))
        sendASR(file_url, language, words_per_line, file_name, callback, m_use_itn, m_use_capitalize)

def getAllText(data):
    # 初始化空字符串
    full_text = ""

    # 遍历utterances并将text字段拼接起来
    for utterance in data['utterances']:
        full_text += utterance['text'] + " "

    # 去掉最后的额外空格
    return full_text.strip()

# if __name__ == '__main__': 
    # def asr_rsp(file_name, asr_json):
    #     with open(file_name, 'w', encoding="utf-8") as file:
    #         file.write(asr_json)
    # print(sendASR("https://m.mecordai.com/20230321/1.mp3", "en-US", 999999, "D:\\test_video\\_d3\\reddit_font\\1111.txt", asr_rsp))