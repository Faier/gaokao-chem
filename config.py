import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
PAPERS_DIR = os.path.join(DATA_DIR, 'papers')
DB_PATH = os.path.join(DATA_DIR, 'chem.db')

DEEPSEEK_API_KEY = os.environ.get(
    'DEEPSEEK_API_KEY',
    'sk-66681e1b197e4de2888b2fbc7f17ec48'
)
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'
DEEPSEEK_MODEL = 'deepseek-chat'

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PAPERS_DIR, exist_ok=True)
