from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from models import get_user_by_id, create_user, verify_user, get_user_by_username, is_vip, get_trial_remaining

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


class User:
    """Flask-Login user wrapper with direct VIP properties."""
    def __init__(self, user_dict):
        self.id = user_dict['id']
        self.username = user_dict['username']
        self.is_admin = bool(user_dict.get('is_admin'))
        self.vip_expire_at = user_dict.get('vip_expire_at')
        self.trial_start = user_dict.get('trial_start')
        self._data = user_dict

    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id

    def has_vip(self):
        return is_vip(self._data)

    def trial_remaining_hours(self):
        return get_trial_remaining(self._data)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = verify_user(username, password)
        if user:
            login_user(User(user), remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('用户名或密码错误', 'error')
    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        if len(username) < 2 or len(username) > 32:
            flash('用户名长度 2-32 个字符', 'error')
        elif len(password) < 6:
            flash('密码至少 6 位', 'error')
        elif password != confirm:
            flash('两次密码不一致', 'error')
        elif get_user_by_username(username):
            flash('用户名已存在', 'error')
        else:
            create_user(username, password)
            user = get_user_by_username(username)
            login_user(User(user), remember=True)
            return redirect(url_for('index'))
    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
