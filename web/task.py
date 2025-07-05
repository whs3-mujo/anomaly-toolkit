# app/tasks.py
import uuid, os, time
from threading import Thread
from .ai_script import detect_anomalies

# 메모리 내 태스크 저장소
_tasks = {}

def start_task(file_path):
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "filename": os.path.basename(file_path),
        "progress": 0,
        "result_html": None,
    }
    Thread(target=_run, args=(task_id, file_path), daemon=True).start()
    return task_id

def _run(task_id, file_path):
    # 1) 시작 표시
    _tasks[task_id]["progress"] = 5

    # 2) 실제 AI 탐지 함수 호출
    #    detect_anomalies는 file_path만 받아 HTML 문자열을 반환합니다.
    html = detect_anomalies(file_path)

    # 3) 중간 진척도를 80% → 100% 로 올려 줘도 되고
    _tasks[task_id]["progress"] = 80
    time.sleep(0.2)  # (필요 시)

    # 4) 결과 저장
    _tasks[task_id]["result_html"] = html
    _tasks[task_id]["progress"]    = 100

def get_progress(task_id):
    return _tasks.get(task_id, {}).get("progress", 0)

def get_info(task_id):
    return _tasks.get(task_id, {})
