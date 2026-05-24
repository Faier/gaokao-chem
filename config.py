import os
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
PAPERS_DIR = os.path.join(DATA_DIR, 'papers')
UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')
DB_PATH = os.path.join(DATA_DIR, 'chem.db')

SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))

DEEPSEEK_API_KEY = os.environ.get(
    'DEEPSEEK_API_KEY',
    'sk-66681e1b197e4de2888b2fbc7f17ec48'
)
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'
DEEPSEEK_MODEL = 'deepseek-chat'

# VIP 配置
TRIAL_HOURS = 24          # 试用时长（小时）
VIP_CODE_LENGTH = 16      # 激活码长度
DEFAULT_PAGE_SIZE = 15    # 默认每页条数

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PAPERS_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
