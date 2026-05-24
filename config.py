import os
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
PAPERS_DIR = os.path.join(DATA_DIR, 'papers')
UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')
DB_PATH = os.path.join(DATA_DIR, 'chem.db')

def _get_secret_key():
    """Get SECRET_KEY from env or persistent file."""
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    key_file = os.path.join(DATA_DIR, '.secret_key')
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(key_file):
        with open(key_file) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(key_file, 'w') as f:
        f.write(key)
    return key


SECRET_KEY = _get_secret_key()

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
