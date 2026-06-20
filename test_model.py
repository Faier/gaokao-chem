import sys
sys.path.insert(0, r'd:\Claude\gaokao-chem')

from config import MIMO_API_KEY, MIMO_API_URL, MIMO_MODEL
print('API KEY:', MIMO_API_KEY[:8] + '...' if MIMO_API_KEY else '(empty - 未配置)')
print('API URL:', MIMO_API_URL)
print('MODEL:', MIMO_MODEL)
print()

if not MIMO_API_KEY:
    print('ERROR: API Key 为空，无法测试')
    sys.exit(1)

import requests
import json

payload = {
    "model": MIMO_MODEL,
    "messages": [
        {"role": "user", "content": "请回复 {\"ok\": true}，只返回这个JSON，不要其他内容"}
    ],
    "max_tokens": 100,
    "temperature": 0,
}
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {MIMO_API_KEY}",
}

print("正在调用模型...")
try:
    resp = requests.post(MIMO_API_URL, headers=headers, json=payload, timeout=30)
    print(f"HTTP 状态码: {resp.status_code}")
    if resp.status_code != 200:
        print("错误响应:", resp.text[:500])
    else:
        result = resp.json()
        content = result["choices"][0]["message"]["content"]
        print(f"模型回复: {repr(content)}")
except requests.Timeout:
    print("ERROR: 请求超时（30s）")
except Exception as e:
    print(f"ERROR: {e}")
