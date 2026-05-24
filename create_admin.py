"""CLI script to create an admin user."""
import sys
from models import init_db, create_user

if len(sys.argv) < 3:
    print('Usage: python create_admin.py <username> <password>')
    sys.exit(1)

init_db()
username = sys.argv[1]
password = sys.argv[2]
create_user(username, password, is_admin=1)
print(f'Admin user "{username}" created.')
