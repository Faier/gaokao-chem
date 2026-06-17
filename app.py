import logging
import os

from flask import Flask, render_template, send_from_directory
from flask_login import LoginManager, current_user

from config import SECRET_KEY, DATA_DIR
from models import init_db, get_user_by_id

app = Flask(__name__)
app.secret_key = SECRET_KEY
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logging.getLogger('parser').setLevel(logging.INFO)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    from auth import User
    user = get_user_by_id(user_id)
    return User(user) if user else None


@app.teardown_appcontext
def close_db(error):
    from flask import g
    db = g.pop('db', None)
    if db is not None:
        db.close()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/images/<path:filename>')
def serve_image(filename):
    """Serve question images stored in data/images/."""
    images_dir = os.path.join(DATA_DIR, 'images')
    return send_from_directory(images_dir, filename)


# Register blueprints
from auth import auth_bp
from vip import vip_bp
from query_bp import query_bp
from admin_bp import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(vip_bp)
app.register_blueprint(query_bp)
app.register_blueprint(admin_bp)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)
