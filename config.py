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


def _read_secret_file(path):
    try:
        with open(path, encoding='utf-8') as f:
            return f.read().strip()
    except OSError:
        return ''


MIMO_API_KEY_FILE = os.environ.get(
    'MIMO_API_KEY_FILE',
    os.path.join(DATA_DIR, '.mimo_api_key')
)
MIMO_API_KEY = (
    os.environ.get('MIMO_API_KEY')
    or os.environ.get('OPENAI_API_KEY')
    or os.environ.get('DEEPSEEK_API_KEY')
    or _read_secret_file(MIMO_API_KEY_FILE)
    or ''
)
MIMO_API_URL = os.environ.get(
    'MIMO_API_URL',
    'https://ark.cn-beijing.volces.com/api/coding/v1/chat/completions'
)
MIMO_MODEL = os.environ.get('MIMO_MODEL', 'doubao-seed-2.0-lite')

# Backward-compatible names used by older code paths.
DEEPSEEK_API_KEY = MIMO_API_KEY
DEEPSEEK_API_URL = MIMO_API_URL
DEEPSEEK_MODEL = MIMO_MODEL

# VIP 配置
TRIAL_HOURS = 24          # 试用时长（小时）
VIP_CODE_LENGTH = 16      # 激活码长度
DEFAULT_PAGE_SIZE = 15    # 默认每页条数

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PAPERS_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
