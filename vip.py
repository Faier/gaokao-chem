from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required, current_user

from models import activate_code

vip_bp = Blueprint('vip', __name__, url_prefix='/api/vip')


@vip_bp.route('/status')
@login_required
def vip_status():
    return jsonify({
        'username': current_user.username,
        'is_admin': current_user.is_admin,
        'vip': current_user.has_vip(),
        'vip_expire_at': current_user.vip_expire_at,
        'trial_remaining_hours': current_user.trial_remaining_hours(),
    })


@vip_bp.route('/activate', methods=['POST'])
@login_required
def activate():
    code = request.form.get('code', '').strip()
    if not code:
        return jsonify({'ok': False, 'msg': '请输入激活码'}), 400
    ok, msg = activate_code(code, current_user.username)
    return jsonify({'ok': ok, 'msg': msg})


@vip_bp.route('/page')
@login_required
def vip_page():
    return render_template('vip.html')
