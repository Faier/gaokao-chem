from flask import Flask, render_template
from flask_login import LoginManager, current_user

from config import SECRET_KEY
from models import init_db, get_user_by_id

app = Flask(__name__)
app.secret_key = SECRET_KEY

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    from auth import User
    user = get_user_by_id(user_id)
    return User(user) if user else None


@app.route('/')
def index():
    return render_template('index.html')


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
