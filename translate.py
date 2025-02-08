# import json

# from volcengine.ApiInfo import ApiInfo
# from volcengine.Credentials import Credentials
# from volcengine.ServiceInfo import ServiceInfo
# from volcengine.base.Service import Service

# k_access_key = 'AKLTYWVhYTFmNDA3Nzk3NGVjMjlkNmNhYWMzNjc2NzdjZGY' # https://console.volcengine.com/iam/keymanage/
# k_secret_key = 'TlRVeE1XWmpNams1WTJFMU5EWTRaRGczTXpGaVl6WmxOalkyWlRkaFlXSQ=='
# k_service_info = \
#     ServiceInfo('translate.volcengineapi.com',
#                 {'Content-Type': 'application/json'},
#                 Credentials(k_access_key, k_secret_key, 'translate', 'cn-north-1'),
#                 5,
#                 5)
# k_query = {
#     'Action': 'TranslateText',
#     'Version': '2020-06-01'
# }
# k_api_info = {
#     'translate': ApiInfo('POST', '/', k_query, {}, {})
# }
# service = Service(k_service_info, k_api_info)

# def get(chat_list, language):
#     m_language = 'en'
#     if language == 'es-MX':
#         m_language = 'es'
#     elif language == 'ru-RU':
#         m_language = 'ru'

#     body = {
#         'TargetLanguage': m_language,
#         'TextList': chat_list,
#     }

#     return service.json('translate', {}, json.dumps(body))
import deepl

def get(chat_list, language):
    m_language = 'EN-US'
    if language == 'es-MX':
        m_language = 'ES'
    elif language == 'ru-RU':
        m_language = 'RU'
    elif language == 'zh-CN':
        m_language = 'ZH'

    auth_key = "96e67760-e4b4-4e47-a1c0-b0ce2d8f152f"  # Replace with your key
    translator = deepl.Translator(auth_key)
    result = translator.translate_text(chat_list, target_lang=m_language)
    return [item.text for item in result]