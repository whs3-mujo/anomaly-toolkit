# app/web/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app
from werkzeug.utils import secure_filename
import os

from .task import start_task, get_progress, get_info

bp = Blueprint('web', __name__, template_folder='templates/web')

# 1) 업로드 화면
@bp.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        f = request.files.get('logfile')
        if not f:
            return render_template('upload.html', error="파일을 선택하세요")
        filename = secure_filename(f.filename)
        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'data')
        os.makedirs(upload_dir, exist_ok=True)
        path = os.path.join(upload_dir, filename)
        f.save(path)

        task_id = start_task(path)
        return redirect(url_for('web.progress', task_id=task_id))

    return render_template('upload.html')

# 2) 진행률 페이지
@bp.route('/upload/<task_id>/progress')
def progress(task_id):
    return render_template('progress.html', task_id=task_id)

# 3) AJAX로 진행률 가져오기
@bp.route('/upload/<task_id>/status')
def status(task_id):
    prog = get_progress(task_id)
    return jsonify({"progress": prog})

# 4) 파일 세부 정보 API
@bp.route('/upload/<task_id>/info')
def info(task_id):
    return jsonify(get_info(task_id))
