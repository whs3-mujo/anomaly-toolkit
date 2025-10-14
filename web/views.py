from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .forms import UploadFileForm
from .models import AnalysisSession, AnomalyLog
import uuid
import json
import os
from django.conf import settings
import pandas as pd
import numpy as np
import shap
import matplotlib
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import platform
import time
import threading
from .ai.ai_script import detect_anomalies
from .ai.visualize_graph import plot_anomaly_by_hour, plot_anomaly_by_user, plot_anomaly_score_distribution
from django.db.models import Count, Q
from django.contrib.auth.models import User

# 한글 폰트 설정 (다양한 환경 지원)
matplotlib.use('Agg')
matplotlib.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지

# 플랫폼별 한글 폰트 설정
if platform.system() == 'Windows':
    try:
        matplotlib.rc('font', family='Malgun Gothic')
    except:
        try:
            matplotlib.rc('font', family='NanumGothic')
        except:
            matplotlib.rc('font', family='DejaVu Sans')
            print("한글 폰트를 찾을 수 없어 기본 폰트를 사용합니다.")
elif platform.system() == 'Darwin':  # macOS
    matplotlib.rc('font', family='AppleGothic')
else:  # Linux/Docker
    try:
        matplotlib.rc('font', family='NanumGothic')
    except:
        matplotlib.rc('font', family='DejaVu Sans')
        print("한글 폰트를 찾을 수 없어 기본 폰트를 사용합니다.")


def redirect_dashboard(request):
    return redirect('web:dashboard')

def dashboard_view(request):
    return render(request, 'web/dashboard.html')

def get_analysis_history(request):
    """분석 히스토리 목록 반환"""
    try:
        sessions = AnalysisSession.objects.all().order_by('-created_at')
        history_data = []
        for session in sessions:
            history_data.append({
                'id': session.id,
                'session_id': session.session_id,
                'filename': session.get_short_filename(),
                'full_filename': session.original_filename,
                'file_type': session.file_type,
                'created_at': session.created_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
            })
        return JsonResponse({
            'success': True,
            'history': history_data,
            'total': len(history_data)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)

@require_http_methods(["GET"])
def get_analysis_detail(request, session_id):
    """특정 분석 결과 상세 정보 반환"""
    try:
        session = get_object_or_404(AnalysisSession, session_id=session_id)
        
        analysis_result = session.analysis_result.copy() if session.analysis_result else {}
        analysis_result['text_html'] = generate_interactive_summary_html(session)
        
        return JsonResponse({
            'success': True,
            'session': {
                'id': session.id,
                'session_id': session.session_id,
                'filename': session.original_filename,
                'file_type': session.file_type,
                'created_at': session.created_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'analysis_result': analysis_result,
                'user_graph_html': getattr(session, 'user_graph_html', None),
                'hour_graph_html': getattr(session, 'hour_graph_html_top3', None),
                'score_graph_html': getattr(session, 'score_graph_html', None),
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)

def delete_session_files(session):
    """세션과 관련된 모든 파일 삭제"""
    import glob
    
    try:
        files_to_delete = []
        
        # 1. 세션의 기본 파일 경로
        if session.file_path and os.path.exists(session.file_path):
            files_to_delete.append(session.file_path)
        
        # 2. analysis_result에서 파일 경로들 수집
        if hasattr(session, 'analysis_result') and session.analysis_result:
            result = session.analysis_result
            
            # 결과 CSV 파일들
            result_csv_path = result.get('result_csv_path')
            if result_csv_path and os.path.exists(result_csv_path):
                files_to_delete.append(result_csv_path)
            
            # SHAP 관련 파일들
            shap_csv_path = result.get('shap_csv_path')
            shap_npy_path = result.get('shap_npy_path')
            
            if shap_csv_path and os.path.exists(shap_csv_path):
                files_to_delete.append(shap_csv_path)
            if shap_npy_path and os.path.exists(shap_npy_path):
                files_to_delete.append(shap_npy_path)
            
            # result_csv_path에서 관련 파일들 유추
            if result_csv_path:
                base_path = result_csv_path.replace('_full_data_with_anomaly_info_readable.csv', '')
                base_path = base_path.replace('_full_data_with_anomaly_info.csv', '')
                
                # 관련 파일 패턴들
                patterns = [
                    base_path + '_*.csv',
                    base_path + '_*.npy',
                    base_path + '_*.pkl',
                ]
                
                for pattern in patterns:
                    matching_files = glob.glob(pattern)
                    files_to_delete.extend(matching_files)
        
        # 3. 파일명에서 타임스탬프 기반으로 관련 파일 찾기
        if session.file_path:
            import re
            timestamp_match = re.search(r'(\d{8}_\d{6})', session.file_path)
            if timestamp_match:
                timestamp = timestamp_match.group(1)
                upload_dir = os.path.dirname(session.file_path)
                base_name = "Final_Fintech_Security_Logs"
                
                # 타임스탬프 기반 관련 파일들
                timestamp_patterns = [
                    os.path.join(upload_dir, f"{base_name}_{timestamp}_*.csv"),
                    os.path.join(upload_dir, f"{base_name}_{timestamp}_*.npy"),
                    os.path.join(upload_dir, f"{base_name}_{timestamp}_*.pkl"),
                ]
                
                for pattern in timestamp_patterns:
                    matching_files = glob.glob(pattern)
                    files_to_delete.extend(matching_files)
        
        # 중복 제거
        files_to_delete = list(set(files_to_delete))
        
        # 파일 삭제 실행
        deleted_count = 0
        for file_path in files_to_delete:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
                    print(f"파일 삭제 성공: {file_path}")
            except Exception as e:
                print(f"파일 삭제 실패 ({file_path}): {e}")
        
        print(f"세션 {session.session_id}: 총 {deleted_count}개 파일 삭제 완료")
        
    except Exception as e:
        print(f"세션 파일 삭제 중 오류 발생: {e}")

def create_analysis_session(filename, file_path, file_type, analysis_result):
    """새로운 분석 세션 생성 (완료된 분석 결과와 함께)"""
    session_id = str(uuid.uuid4())
    analysis_session = AnalysisSession.objects.create(
        session_id=session_id,
        original_filename=filename,
        file_path=file_path,
        file_type=file_type,
        analysis_result=analysis_result
    )
    return analysis_session

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_analysis_session(request, session_id):
    """분석 세션 삭제 (관련 파일들도 함께 삭제)"""
    try:
        session = get_object_or_404(AnalysisSession, session_id=session_id)
        
        # 세션과 관련된 모든 파일 삭제
        delete_session_files(session)
        
        session.delete()
        return JsonResponse({'success': True, 'message': '분석 기록과 관련 파일들이 삭제되었습니다.'})
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def rename_analysis_session(request, session_id):
    """분석 세션 이름 변경"""
    try:
        session = get_object_or_404(AnalysisSession, session_id=session_id)
        data = json.loads(request.body)
        new_filename = data.get('filename', '').strip()
        if not new_filename:
            return JsonResponse({'success': False, 'error': '파일명을 입력해주세요.'}, status=400)
        session.original_filename = new_filename
        session.save()
        return JsonResponse({'success': True, 'message': '파일명이 변경되었습니다.'})
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)

@require_http_methods(["GET", "POST"])
def upload_view(request):
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            file = form.cleaned_data['datafile']
            try:
                save_dir = os.path.join(settings.MEDIA_ROOT, "uploads")
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.join(save_dir, file.name)
                with open(save_path, "wb+") as dest:
                    for chunk in file.chunks():
                        dest.write(chunk)

                analysis_result = detect_anomalies(save_path)

                # 업로드만 하는 경우에는 그래프 저장하지 않음
                AnalysisSession.objects.create(
                    session_id=str(uuid.uuid4()),
                    original_filename=file.name,
                    file_path=save_path,
                    file_type=os.path.splitext(file.name)[-1][1:].upper(),
                    analysis_result=analysis_result,
                )
                return redirect("web:dashboard")
            except Exception as e:
                return render(request, "web/upload.html", {"form": form, "error": str(e)})
        else:
            pass  # 폼이 유효하지 않음
    else:
        form = UploadFileForm()
    return render(request, "web/upload.html", {"form": form})

def preview_columns(request):
    """
    업로드된 파일에서 칼럼명과 데이터 미리보기(2줄) 반환
    """
    if request.method == "POST" and request.FILES.get("file"):
        file = request.FILES["file"]
        try:
            df = None
            
            # 파일 크기 체크 (100MB 제한)
            if file.size > 100 * 1024 * 1024:  # 100MB
                return JsonResponse({
                    "error": "파일이 너무 큽니다. 100MB 이하의 파일만 업로드 가능합니다."
                }, status=400)
            
            # 여러 인코딩 시도
            for enc in ["utf-8", "cp949", "euc-kr", "latin1"]:
                try:
                    file.seek(0)  # 파일 포인터 리셋
                    # 처음 몇 줄만 읽어서 미리보기 생성
                    df = pd.read_csv(file, nrows=5, encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    continue
            else:
                return JsonResponse({
                    "error": "지원하지 않는 파일 인코딩입니다. UTF-8, CP949, EUC-KR, Latin1 인코딩을 지원합니다."
                }, status=400)
            
            if df is None or df.empty:
                return JsonResponse({
                    "error": "파일이 비어있거나 읽을 수 있는 데이터가 없습니다."
                }, status=400)
            
            # 컬럼 수 제한 (성능상 이유)
            if len(df.columns) > 100:
                return JsonResponse({
                    "error": f"컬럼이 너무 많습니다 ({len(df.columns)}개). 최대 100개 컬럼까지 지원합니다."
                }, status=400)
            
            # 컬럼명 정제 (공백 제거, 특수문자 처리)
            original_columns = list(df.columns)
            cleaned_columns = []
            
            for col in original_columns:
                # 컬럼명이 비어있으면 기본값 설정
                if pd.isna(col) or str(col).strip() == '':
                    cleaned_columns.append(f"Column_{len(cleaned_columns)}")
                else:
                    # 컬럼명 정제
                    clean_col = str(col).strip()
                    cleaned_columns.append(clean_col)
            
            df.columns = cleaned_columns
            
            # 데이터 품질 체크
            total_cells = df.shape[0] * df.shape[1]
            null_cells = df.isnull().sum().sum()
            null_ratio = null_cells / total_cells if total_cells > 0 else 0
            
            # 결측치가 너무 많으면 경고
            quality_warnings = []
            if null_ratio > 0.8:
                quality_warnings.append(f"데이터의 {null_ratio:.1%}가 결측치입니다.")
            
            # 모든 컬럼이 결측치인 경우 체크
            empty_columns = [col for col in df.columns if df[col].isnull().all()]
            if empty_columns:
                quality_warnings.append(f"빈 컬럼이 {len(empty_columns)}개 있습니다: {', '.join(empty_columns[:5])}")
            
            # 미리보기 데이터 생성 (최대 2행)
            preview_df = df.head(2)
            
            # NaN 값을 빈 문자열로 표시
            preview_dict = []
            for _, row in preview_df.iterrows():
                row_dict = {}
                for col in df.columns:
                    value = row[col]
                    if pd.isna(value):
                        row_dict[col] = ""  # 빈 문자열로 변경
                    else:
                        # 문자열이 너무 길면 자르기
                        str_value = str(value)
                        if len(str_value) > 50:
                            row_dict[col] = str_value[:47] + "..."
                        else:
                            row_dict[col] = str_value
                preview_dict.append(row_dict)
            
            response_data = {
                "columns": cleaned_columns, 
                "preview": preview_dict,
                "total_columns": len(cleaned_columns),
                "sample_rows": len(preview_df)
            }
            
            # 품질 경고가 있으면 추가
            if quality_warnings:
                response_data["warnings"] = quality_warnings
            
            return JsonResponse(response_data)
            
        except pd.errors.EmptyDataError:
            return JsonResponse({
                "error": "파일이 비어있습니다. 데이터가 포함된 CSV 파일을 업로드해주세요."
            }, status=400)
        except pd.errors.ParserError as e:
            return JsonResponse({
                "error": f"CSV 파일 형식이 올바르지 않습니다: {str(e)}"
            }, status=400)
        except Exception as e:
            print(f"파일 미리보기 중 예상치 못한 오류: {e}")
            return JsonResponse({
                "error": f"파일 처리 중 오류가 발생했습니다: {str(e)}"
            }, status=400)
    
    return JsonResponse({"error": "파일이 업로드되지 않았습니다."}, status=400)

def detect_anomalies_view(request):
    try:
        if request.method == "POST":
            file = request.FILES["file"]
            exclude_columns = request.POST.get("exclude_columns", "")
            exclude_columns = [col.strip() for col in exclude_columns.split(",") if col.strip()]
            user_col = request.POST.get("user_col")
            time_col = request.POST.get("time_col")
            
            # q(이상치 비율)값 받기
            q_value = request.POST.get("q", "0.05")
            try:
                q = float(q_value)
                # 범위 제한 (1%~50%)
                q = max(0.01, min(0.5, q))
            except (ValueError, TypeError):
                q = 0.05  # 오류 시 기본값
            
            # 빈 문자열을 None으로 변환
            user_col = user_col if user_col else None
            time_col = time_col if time_col else None
            file_path = save_uploaded_file(file)
            
            # 타임아웃 설정 (10분)
            timeout = 600  # 초 단위
            
            # 결과 변수 및 에러 플래그
            result = None
            analysis_error = False
            
            def run_analysis():
                nonlocal result, analysis_error
                try:
                    result = detect_anomalies(file_path, exclude_columns, user_col=user_col, time_col=time_col, q=q)
                except Exception as e:
                    analysis_error = True
                    print(f"분석 중 오류 발생: {e}")
            
            # 분석 쓰레드 시작
            analysis_thread = threading.Thread(target=run_analysis)
            analysis_thread.start()
            
            # 지정된 시간만큼 대기
            analysis_thread.join(timeout)
            
            # 타임아웃 발생 시
            if analysis_thread.is_alive() or analysis_error or result is None:
                return JsonResponse({
                    'success': False, 
                    'error': '처리할 수 없는 데이터셋입니다. 10분 이상 소요되었거나 분석 중 오류가 발생했습니다.'
                }, status=408)  # 408 Request Timeout

            result_csv_path = result.get("result_csv_path")
            df_result = pd.read_csv(result_csv_path)

            # === 그래프 HTML 사용  ===
            user_graph_html = result.get('user_graph_html')
            score_graph_html = result.get('score_distribution_html')
            if user_col and time_col and user_col in df_result.columns and time_col in df_result.columns:
                hour_graph_html_top3 = plot_anomaly_by_hour(df_result, user_col, time_col, top_n=3)
                hour_graph_html_top10 = plot_anomaly_by_hour(df_result, user_col, time_col, top_n=10)
            else:
                hour_graph_html_top3 = None
                hour_graph_html_top10 = None

            AnalysisSession.objects.create(
                session_id=str(uuid.uuid4()),
                original_filename=file.name,
                file_path=file_path,
                file_type=os.path.splitext(file.name)[-1][1:].upper(),
                analysis_result=result,
                user_col=user_col,
                time_col=time_col,
                user_graph_html=user_graph_html,
                hour_graph_html_top3=hour_graph_html_top3,
                hour_graph_html_top10=hour_graph_html_top10,
                score_graph_html=score_graph_html,
            )
            return JsonResponse(result)
        
        return JsonResponse({"error": "Invalid request"}, status=400)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({"error": str(e)},status=500)

@require_http_methods(["GET"])
def upload_filter_view(request):
    return render(request, "web/upload_filter.html")

def save_uploaded_file(file):
    upload_dir = os.path.join(settings.MEDIA_ROOT, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.name)
    with open(file_path, "wb+") as destination:
        for chunk in file.chunks():
            destination.write(chunk)
    return file_path

@require_http_methods(["GET"])
def download_analysis_csv(request, session_id):
    session = get_object_or_404(AnalysisSession, session_id=session_id)
    result = session.analysis_result or {}

    download_type = request.GET.get("type", "anomaly")
    
    if download_type == "all":
        # 전체 데이터: 원본 업로드 파일 순서 그대로, Anomaly 라벨만 추가
        try:
            import os
            result_csv_path = result.get("result_csv_path")
            if result_csv_path and os.path.exists(result_csv_path):
                df = pd.read_csv(result_csv_path)
                
                # 원본 파일에서 인덱스 순서 복원 (업로드 순서)
                # TF-IDF 컬럼 제거
                tfidf_cols = [col for col in df.columns if '_tfidf_' in col]
                df_clean = df.drop(columns=tfidf_cols, errors='ignore')
                
                # 원본 순서대로 정렬 (index 기준)
                df_original_order = df_clean.sort_index()
                
                csv_data = df_original_order.to_csv(index=False, encoding="utf-8-sig")
                
                base_name = session.original_filename
                if base_name.lower().endswith('.csv'):
                    base_name = base_name[:-4]
                filename = f"{base_name}_전체.csv"
                
                response = HttpResponse(csv_data, content_type="text/csv; charset=utf-8-sig")
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
        except Exception as e:
            print(f"전체 데이터 다운로드 중 오류: {e}")
        
        # analysis_result에서 가져오기
        records = result.get("all_records", [])
    else:
        # 이상치만: 이상치 점수가 높은 순서대로 (대시보드 표와 동일)
        records = result.get("records", [])

    if not records:
        return HttpResponse("다운로드할 데이터가 없습니다.", status=404)

    df = pd.DataFrame(records)
    csv_data = df.to_csv(index=False, encoding="utf-8-sig")
    
    base_name = session.original_filename
    if base_name.lower().endswith('.csv'):
        base_name = base_name[:-4]
    filename = f"{base_name}_{'전체' if download_type == 'all' else '이상치'}.csv"
    
    response = HttpResponse(csv_data, content_type="text/csv; charset=utf-8-sig")
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

# get_shap_plot 함수를 선언하여 SHAP그래프를 생성 및 이미지 파일 만듦 / 그래프 모양, 크기를 여기서 바꿀 수 있음

def get_shap_plot(request, session_id, row_index):
    session = get_object_or_404(AnalysisSession, session_id=session_id)
    
    # 원본 데이터 로드 (실제 칼럼 확인용)
    try:
        original_df = pd.read_csv(session.file_path)
        original_columns = set(original_df.columns)
    except (FileNotFoundError, pd.errors.EmptyDataError, pd.errors.ParserError):
        original_df = None
        original_columns = set()
    
    # 데이터 불러오기 - SHAP 파일 경로 올바르게 생성
    try:
        # analysis_result에서 올바른 파일 경로들 가져오기
        if hasattr(session, 'analysis_result') and session.analysis_result:
            print(f"DEBUG: analysis_result 키들: {list(session.analysis_result.keys())}")
            
            # 다양한 키 이름으로 SHAP 파일 경로 찾기
            shap_csv_path = (session.analysis_result.get('shap_csv_path') or 
                           session.analysis_result.get('X_for_shap_path') or
                           session.analysis_result.get('shap_x_path'))
            shap_npy_path = (session.analysis_result.get('shap_npy_path') or 
                           session.analysis_result.get('shap_values_path') or
                           session.analysis_result.get('shap_path'))
            
            # result_csv_path에서 경로 유추해보기
            result_csv_path = session.analysis_result.get('result_csv_path')
            if result_csv_path and (not shap_csv_path or not shap_npy_path):
                base_path = result_csv_path.replace('_full_data_with_anomaly_info_readable.csv', '')
                base_path = base_path.replace('_full_data_with_anomaly_info.csv', '')
                potential_shap_csv = base_path + '_X_for_shap.csv'
                potential_shap_npy = base_path + '_shap_values.npy'
                
                print(f"DEBUG: result_csv_path에서 유추한 경로:")
                print(f"  CSV: {potential_shap_csv}, 존재: {os.path.exists(potential_shap_csv)}")
                print(f"  NPY: {potential_shap_npy}, 존재: {os.path.exists(potential_shap_npy)}")
                
                if os.path.exists(potential_shap_csv) and os.path.exists(potential_shap_npy):
                    shap_csv_path = potential_shap_csv
                    shap_npy_path = potential_shap_npy
            
            print(f"DEBUG: 최종 SHAP 파일 경로:")
            print(f"  CSV: {shap_csv_path}")
            print(f"  NPY: {shap_npy_path}")
            
            if shap_csv_path and shap_npy_path and os.path.exists(shap_csv_path) and os.path.exists(shap_npy_path):
                print(f"DEBUG: SHAP 파일 로드 성공!")
                X = pd.read_csv(shap_csv_path)
                shap_values = np.load(shap_npy_path)
            else:
                # fallback: 현재 세션 파일에서 올바른 타임스탬프 추출
                current_file = session.file_path
                print(f"DEBUG: 현재 세션 파일 경로: {current_file}")
                
                # 파일명에서 타임스탬프 패턴 추출 (20251014_144206 형태)
                import re
                timestamp_match = re.search(r'(\d{8}_\d{6})', current_file)
                
                if timestamp_match:
                    timestamp = timestamp_match.group(1)
                    base_name = "Final_Fintech_Security_Logs"
                    upload_dir = os.path.dirname(current_file)
                    
                    shap_csv_path = os.path.join(upload_dir, f"{base_name}_{timestamp}_X_for_shap.csv")
                    shap_npy_path = os.path.join(upload_dir, f"{base_name}_{timestamp}_shap_values.npy")
                    
                    print(f"DEBUG: 생성된 SHAP 파일 경로들:")
                    print(f"  CSV: {shap_csv_path}")
                    print(f"  NPY: {shap_npy_path}")
                    print(f"  CSV 존재: {os.path.exists(shap_csv_path)}")
                    print(f"  NPY 존재: {os.path.exists(shap_npy_path)}")
                else:
                    # 타임스탬프가 없는 경우 원본 방식 사용
                    base_path = current_file
                    if "_full_data_with_anomaly_info" in base_path:
                        if "_readable.csv" in base_path:
                            base_path = base_path.replace("_full_data_with_anomaly_info_readable.csv", ".csv")
                        elif "_full_data_with_anomaly_info.csv" in base_path:
                            base_path = base_path.replace("_full_data_with_anomaly_info.csv", ".csv")
                    
                    shap_csv_path = base_path.replace(".csv", "_X_for_shap.csv")
                    shap_npy_path = base_path.replace(".csv", "_shap_values.npy")
                
                if not os.path.exists(shap_csv_path) or not os.path.exists(shap_npy_path):
                    # 업로드 디렉토리에서 해당 세션과 매칭되는 SHAP 파일들 찾기
                    upload_dir = os.path.dirname(current_file)
                    available_files = os.listdir(upload_dir)
                    
                    # 세션의 생성시간과 가장 가까운 SHAP 파일 찾기
                    session_created = session.created_at
                    print(f"DEBUG: 세션 생성시간: {session_created}")
                    
                    # 사용 가능한 SHAP 파일들에서 타임스탬프 추출
                    shap_files_info = []
                    for f in available_files:
                        if '_X_for_shap.csv' in f:
                            timestamp_match = re.search(r'(\d{8}_\d{6})', f)
                            if timestamp_match:
                                timestamp_str = timestamp_match.group(1)
                                # 타임스탬프를 datetime으로 변환
                                try:
                                    from datetime import datetime
                                    file_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                                    shap_files_info.append({
                                        'timestamp': timestamp_str,
                                        'file_time': file_time,
                                        'csv_file': f,
                                        'npy_file': f.replace('_X_for_shap.csv', '_shap_values.npy')
                                    })
                                except ValueError:
                                    continue
                    
                    # 세션 생성시간과 가장 가까운 SHAP 파일 선택
                    if shap_files_info:
                        # 세션 시간 이후의 파일 중 가장 가까운 것 선택
                        valid_files = [f for f in shap_files_info if f['file_time'] >= session_created.replace(tzinfo=None)]
                        if not valid_files:
                            # 세션 시간 이후 파일이 없으면 가장 최근 파일 사용
                            valid_files = shap_files_info
                        
                        closest_file = min(valid_files, key=lambda x: abs((x['file_time'] - session_created.replace(tzinfo=None)).total_seconds()))
                        
                        shap_csv_path = os.path.join(upload_dir, closest_file['csv_file'])
                        shap_npy_path = os.path.join(upload_dir, closest_file['npy_file'])
                        
                        print(f"DEBUG: 매칭된 SHAP 파일:")
                        print(f"  CSV: {shap_csv_path}")
                        print(f"  NPY: {shap_npy_path}")
                        
                        if not os.path.exists(shap_csv_path) or not os.path.exists(shap_npy_path):
                            matching_shap_files = [f for f in available_files if '_X_for_shap.csv' in f or '_shap_values.npy' in f]
                            raise FileNotFoundError(f"매칭된 SHAP 파일을 찾을 수 없습니다.\n예상 경로: {shap_csv_path}, {shap_npy_path}\n사용 가능한 SHAP 파일들: {matching_shap_files}")
                    else:
                        matching_shap_files = [f for f in available_files if '_X_for_shap.csv' in f or '_shap_values.npy' in f]
                        raise FileNotFoundError(f"SHAP 파일을 찾을 수 없습니다.\n예상 경로: {shap_csv_path}, {shap_npy_path}\n사용 가능한 SHAP 파일들: {matching_shap_files}")
                
                X = pd.read_csv(shap_csv_path)
                shap_values = np.load(shap_npy_path)
        else:
            raise ValueError("분석 결과가 없습니다")
            
    except Exception as e:
        print(f"SHAP 파일 로딩 오류: {e}")
        return JsonResponse({
            'success': False,
            'error': f'SHAP 데이터를 불러올 수 없습니다: {str(e)}'
        }, status=500)
    
    feature_cols = X.columns.tolist()
    
    # row(1개 샘플에 대한 shap vector) 안전 추출
    # shap_loaded의 가능한 형태를 모두 커버:
    # - 2D ndarray: (n_samples, n_features)
    # - 3D ndarray: (n_classes, n_samples, n_features)
    # - object/리스트: [ (n_samples, n_features), ... ] 또는 list-of-arrays
    if isinstance(shap_values, np.ndarray) and shap_values.dtype != object:
        if shap_values.ndim == 2:
            row = shap_values[int(row_index)]
        elif shap_values.ndim == 3:
            row = shap_values[0, int(row_index), :]  # 첫 클래스 사용
        else:
            # 예외 형태는 1D로 간주되지 않도록 방어
            row = np.atleast_1d(shap_values[int(row_index)])
    else:
        # object array 혹은 list
        shap_list = shap_values.tolist() if isinstance(shap_values, np.ndarray) else shap_values
        if isinstance(shap_list, list):
            # 첫 요소가 (n_samples, n_features)인 경우를 우선 가정
            if len(shap_list) > 0 and isinstance(shap_list[0], (np.ndarray, list)):
                first = np.asarray(shap_list[0])
                if first.ndim == 2:
                    row = np.asarray(shap_list[0][int(row_index)])
                elif first.ndim == 3:
                    row = np.asarray(shap_list[0][0, int(row_index), :])
                else:
                    row = np.asarray(shap_list[0]).reshape(-1)
            else:
                # 예외적으로 (n_samples, n_features)가 바로 들어온 경우
                row = np.asarray(shap_list[int(row_index)]).reshape(-1)
        else:
            row = np.asarray(shap_list).reshape(-1)

    row = np.asarray(row).ravel()  # 1D 보장

    # 길이 정합성 강제: feature_cols vs row vs X.iloc[row_index]
    if len(feature_cols) != len(row) or X.shape[1] != len(feature_cols):
        print(f"[WARN] SHAP/특성 길이 불일치 -> 정합화 "
              f"(features={len(feature_cols)}, shap={len(row)}, Xcols={X.shape[1]})")
    min_len = min(len(feature_cols), len(row), X.shape[1])
    feature_cols = feature_cols[:min_len]
    row = row[:min_len]
    X = X.iloc[:, :min_len]

    # 이제 정합성 보장 후, 단 한 번만 shap_df 생성
    shap_df = pd.DataFrame({
        'feature': feature_cols,
        'shap_value': row,
        'abs_val': np.abs(row),
        'data': X.iloc[int(row_index)].values
    })

    # TF-IDF 칼럼 식별
    tfidf_cols = [col for col in feature_cols if '_tfidf_' in col]
    
    # TF-IDF 피처 원본 칼럼 찾기 - 원본 데이터셋 참고 
    tfidf_mappings = {}
    lower_original_columns = {col.lower() for col in original_columns}
    for col in tfidf_cols:
        source_col = col.split('_tfidf_')[0]
        if source_col.lower() in lower_original_columns:
            # 실제 원본 컬럼명으로 표시
            matched_col = [col for col in original_columns if col.lower() == source_col.lower()][0]
            display_name = f"{matched_col}"
        else:
            display_name = f"added({source_col})"
        if display_name not in tfidf_mappings:
            tfidf_mappings[display_name] = []
        tfidf_mappings[display_name].append(col)

    # SHAP 값 계산
    row = shap_values[int(row_index)]
    shap_df = pd.DataFrame({
        'feature': feature_cols,
        'shap_value': row,
        'abs_val': np.abs(row),
        'data': X.iloc[int(row_index)].values
    })
    
    # TF-IDF 칼럼을 원본 칼럼으로 통합
    merged_shap_df = []

    # 원본 텍스트 칼럼에 대한 모든 TF-IDF 피처의 영향도 합치기
    for source_col, related_tfidf in tfidf_mappings.items():
        tfidf_rows = shap_df[shap_df['feature'].isin(related_tfidf)]
        total_shap = tfidf_rows['shap_value'].sum()
        
        # 원본 텍스트 칼럼이 있는 경우, 해당 칼럼의 고유값 개수나 길이로 다양성 측정
        if original_df is not None and source_col in original_df.columns:
            original_value = str(original_df[source_col].iloc[int(row_index)])
            # 텍스트 길이나 고유성을 기반으로 한 메트릭 사용
            unique_values = original_df[source_col].nunique()
            current_frequency = (original_df[source_col] == original_value).sum()
            # 희귀도 계산: 전체 개수 대비 현재 값의 빈도
            data_value = 1 - (current_frequency / len(original_df))
        else:
            # 여러 TF-IDF 피처의 data(스케일링 값) 중 가장 크게 벗어난 값 사용
            if not tfidf_rows.empty:
                # Weighted average of 'data' values using absolute SHAP values as weights
                data_value = np.average(tfidf_rows['data'], weights=tfidf_rows['abs_val'])
            else:
                data_value = 0
        
        merged_shap_df.append({
            'feature': f"{source_col}",  # tf-idf 피처를 원본 텍스트 칼럼으로 표시
            'shap_value': total_shap,
            'abs_val': abs(total_shap),
            'data': data_value
        })

    # 나머지 non-TF-IDF 피처 추가
    # 모든 TF-IDF 피처(flatten) 리스트 생성
    all_tfidf_features = [item for sublist in tfidf_mappings.values() for item in sublist]
    non_tfidf_features = [f for f in feature_cols if f not in all_tfidf_features]
    for feature in non_tfidf_features:
        idx = feature_cols.index(feature)
        
        # 원본 데이터에서 해당 특성의 값 가져오기 (가능한 경우)
        if original_df is not None and feature in original_df.columns:
            original_value = original_df[feature].iloc[int(row_index)]
            # 숫자형 데이터의 경우 평균과의 차이 계산
            if pd.api.types.is_numeric_dtype(original_df[feature]):
                mean_value = original_df[feature].mean()
                data_value = abs(original_value - mean_value)
            else:
                # 범주형 데이터의 경우 스케일링된 값 사용
                data_value = abs(X[feature].iloc[int(row_index)])
        else:
            # 원본 데이터에 없는 경우 스케일링된 값 사용
            data_value = abs(X[feature].iloc[int(row_index)])
        
        merged_shap_df.append({
            'feature': feature,
            'shap_value': row[idx],
            'abs_val': abs(row[idx]),
            'data': data_value
        })

    # DataFrame으로 변환
    merged_shap_df = pd.DataFrame(merged_shap_df)
    
    # SHAP < 0인 feature 중 영향 큰 순서대로 정렬
    negative_df = merged_shap_df[merged_shap_df['shap_value'] < 0].sort_values(by='abs_val', ascending=False).reset_index(drop=True)
    # 무조건 6개로 고정되게 리인덱싱 (부족하면 빈 bar로)
    negative_df = negative_df.reindex(range(6)).fillna({
        'feature': '', 'shap_value': 0, 'abs_val': 0, 'data': 0
    })
    max_len = 6  

    y_pos = np.arange(max_len)
    
    # 그래프별 폰트 설정 강화
    plt.rcParams['font.family'] = 'Malgun Gothic' if platform.system() == 'Windows' else 'DejaVu Sans'
    plt.rcParams['axes.unicode_minus'] = False
    
    fig, ax = plt.subplots(figsize=(10, 8))  
    flipped_values = -negative_df['shap_value']  
    max_value = flipped_values.max()
    if max_value > 0:
        ax.set_xlim(0, max_value * 1.2)
    else:
        ax.set_xlim(0, 1)

    ax.barh(y_pos, flipped_values, color='salmon', label='이상치 기여도', align='center', height=0.6)  # height를 0.4로 더 축소
    ax.axvline(x=0, color='black', linewidth=1)

    ax.grid(axis='y', visible=False)  
    ax.grid(axis='x', visible=True, linestyle='--', alpha=0.7)  # 세로줄은 표시

    ax.set_yticks(y_pos)
    ax.set_yticklabels([''] * max_len)
    ax.invert_yaxis()

    for i, (label, value) in enumerate(zip(negative_df['feature'], flipped_values)):
        if label and value > 0:
            text_x = value + (max_value * 0.01) if max_value > 0 else 0.01
            if text_x > max_value * 1.15:
                text_x = max_value * 1.15
                ha = 'right'
            else:
                ha = 'left'
            
            ax.text(text_x, i, label, ha=ha, va='center', 
                   fontsize=9, fontweight='bold',   
                   bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8))  

    ax.set_title(f"{row_index+1}번 ROW", fontweight='bold', fontsize=11, pad=10) 
    ax.set_xlabel("영향도 크기 (SHAP)", fontsize=10) 
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), frameon=False, fontsize=9)  

    plt.tight_layout()
    plt.subplots_adjust(left=0.02, right=0.98, top=0.85, bottom=0.20)  

    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=100, bbox_inches='tight') 
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    plt.close(fig) 
    
    encoded = base64.b64encode(image_png).decode('utf-8')
    img_html = f'''
    <div style="width: 100%; height: 100%; overflow-y: auto; overflow-x: hidden;">
        <img src="data:image/png;base64,{encoded}" style="width:100%; max-width:100%; height:auto;">
    </div>
    '''
    explanation_html = generate_shap_table(negative_df)    

    middle_html = """
    <div style='margin: 1rem 0; color: #666; font-size: 1.05rem; line-height: 1.5;'>
        이 그래프는 AI가 해당 로그를 이상으로 판단하는 데 영향을 준 항목들을 기여도 순으로 보여줍니다.
    </div>
    """
    description_html = ""
    if hasattr(session, 'analysis_result') and session.analysis_result:
        description_html = session.analysis_result.get('text_html', '')

    return JsonResponse({
        'success': True,
        'plot_html': img_html,
        'shap_middle_html': middle_html,
        'shap_explanation': explanation_html,  
        'description_html': description_html 
    })


def generate_shap_table(shap_df):
    """SHAP 설명을 테이블 형식으로 생성 - 색상별 기여도 표시"""
    table_html = """
    <div style="margin-top: 1rem;">
        <h4 style="color: #1976d2; font-size: 1.25rem; font-weight: 700; margin-bottom: 1rem; border-bottom: 2px solid #e3f2fd; padding-bottom: 0.5rem;">상세 설명</h4>
        <table style="width: 100%; border-collapse: collapse; border: 1px solid #dee2e6;">
            <thead>
                <tr style="background: #f1f3f5;">
                    <th style="padding: 12px 15px; text-align: left; font-weight: 600; color: #495057; border: 1px solid #dee2e6;">컬럼</th>
                    <th style="padding: 12px 15px; text-align: center; font-weight: 600; color: #495057; border: 1px solid #dee2e6;">기여도</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for idx, row in shap_df.head(6).iterrows():
        feature = row['feature']
        if not feature:
            continue
        shap_value = abs(row['shap_value'])
        
        if shap_value > 0.1:
            color = "#c62828"  # 빨간색
            bg_color = "#ffebee"
            level = "높음"
        elif shap_value > 0.05:
            color = "#ef6c00"  # 주황색
            bg_color = "#fff3e0"
            level = "중간"
        elif shap_value > 0.01:
            color = "#f57f17"  # 노란색
            bg_color = "#fffde7"
            level = "약간"
        else:
            color = "#1565c0"  # 파란색
            bg_color = "#e3f2fd"
            level = "미미"
        
        table_html += f"""
        <tr style="background: white;">
            <td style="padding: 10px 15px; border: 1px solid #dee2e6; font-weight: 500; color: #333;">{feature}</td>
            <td style="padding: 10px 15px; border: 1px solid #dee2e6; text-align: center; background: {bg_color}; color: {color}; font-weight: bold; font-size: 1.1rem;">
                {level}<br><small style="font-size: 0.9em; color: #666;">({shap_value:.3f})</small>
            </td>
        </tr>
        """
    
    table_html += """
            </tbody>
        </table>
        <div style="margin-top: 10px; font-size: 0.95em; color: #666; line-height: 1.5;">
            <strong><br>기여도 범례</br></strong> 
            <span style="color: #c62828; font-weight: bold;">높음(0.1↑)</span> | 
            <span style="color: #ef6c00; font-weight: bold;">중간(0.05~0.1)</span> | 
            <br>
            <span style="color: #f57f17; font-weight: bold;">약간(0.01~0.05)</span> | 
            <span style="color: #1565c0; font-weight: bold;">미미(0.01↓)</span>
        </div>
    </div>
    """
    return table_html

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_all_analysis_sessions(request):
    """모든 분석 세션 삭제 (관련 파일들도 함께 삭제)"""
    try:
        sessions = AnalysisSession.objects.all()
        
        # 각 세션의 관련 파일들 삭제
        for session in sessions:
            delete_session_files(session)
        
        # 모든 세션 삭제
        sessions.delete()
        
        return JsonResponse({"success": True, "message": "모든 분석 기록과 관련 파일들이 삭제되었습니다."})
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


from django.shortcuts import get_object_or_404
from .models import AnomalyLog  

def user_anomaly_count(request, username):
    """
    사용자명을 입력받아 해당 사용자가 발생시킨 이상 로그 건수를 반환합니다.
    """
    try:
        # 먼저 해당 사용자가 실제로 존재하는지 확인
        user = User.objects.get(username=username)
        count = AnomalyLog.objects.filter(user=user).count()
        return JsonResponse({'username': username, 'anomaly_count': count})
    except User.DoesNotExist:
        return JsonResponse({'error': '정확한 사용자명을 입력해주세요.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def top_anomaly_users(request, top_n):
    """
    숫자를 입력받아 이상 로그를 많이 발생시킨 상위 N명의 사용자와 로그 건수를 반환합니다.
    """
    session_id = request.GET.get('session_id')
    
    try:
        # session_id가 제공된 경우 해당 세션에서 조회, 없으면 최신 세션 사용
        if session_id:
            session = AnalysisSession.objects.get(session_id=session_id)
        else:
            session = AnalysisSession.objects.filter(
                user_col__isnull=False
            ).order_by('-created_at').first()
        
        if not session:
            return JsonResponse({'error': '분석 세션이 없습니다.'}, status=404)
        
        # 세션의 analysis_result에서 이상치 데이터 조회 (대시보드와 동일한 소스)
        if not session.analysis_result or 'records' not in session.analysis_result:
            return JsonResponse({'error': '분석 결과가 없습니다.'}, status=404)
        
        user_col = session.user_col
        
        # 사용자 컬럼이 설정되지 않았거나 없는 경우
        if not user_col or user_col == "없음":
            return JsonResponse({'error': '사용자 컬럼이 설정되지 않아 상위 사용자를 조회할 수 없습니다.'}, status=400)
            
        anomaly_records = session.analysis_result['records']
        
        if not anomaly_records:
            return JsonResponse({'error': '이상치 데이터가 없습니다.'}, status=404)
        
        # DataFrame으로 변환
        import pandas as pd
        anomaly_df = pd.DataFrame(anomaly_records)
        
        if user_col not in anomaly_df.columns:
            return JsonResponse({'error': '사용자 컬럼이 데이터에 존재하지 않아 상위 사용자를 조회할 수 없습니다.'}, status=400)
        
        # 사용자별 이상 로그 집계
        user_counts = anomaly_df[user_col].value_counts().head(top_n)
        
        # 결과 포맷팅
        formatted_users = [
            {'username': username, 'anomaly_count': int(count)} 
            for username, count in user_counts.items()
        ]
        unique_user_count = len(user_counts)
        
        return JsonResponse({
            'top_users': formatted_users,
            'unique_user_count': unique_user_count
        })
        
    except AnalysisSession.DoesNotExist:
        return JsonResponse({'error': '분석 세션을 찾을 수 없습니다.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': '상위 사용자 조회 중 문제가 발생했습니다. 데이터를 다시 분석해보세요.'}, status=500)

@require_http_methods(["GET"])
def search_anomaly_logs(request):
    """
    특정 사용자의 이상 로그 건수를 검색합니다.
    """
    username = request.GET.get('username', '').strip()
    session_id = request.GET.get('session_id')
    
    if not username:
        return JsonResponse({'error': '검색어를 입력해주세요.'}, status=400)
    
    try:
        # session_id가 제공된 경우 해당 세션에서 검색, 없으면 최신 세션 사용
        if session_id:
            session = AnalysisSession.objects.get(session_id=session_id)
        else:
            session = AnalysisSession.objects.filter(
                user_col__isnull=False
            ).order_by('-created_at').first()
        
        if not session:
            return JsonResponse({'error': '분석 세션이 없습니다.'}, status=404)
        
        # 세션의 analysis_result에서 이상치 데이터 조회 (대시보드와 동일한 소스)
        if not session.analysis_result or 'records' not in session.analysis_result:
            return JsonResponse({'error': '분석 결과가 없습니다.'}, status=404)
        
        user_col = session.user_col
        anomaly_records = session.analysis_result['records']
        
        if not anomaly_records:
            return JsonResponse({'error': '이상치 데이터가 없습니다.'}, status=404)
        
        # DataFrame으로 변환
        import pandas as pd
        anomaly_df = pd.DataFrame(anomaly_records)
        
        if user_col not in anomaly_df.columns:
            return JsonResponse({'error': f'사용자 컬럼 {user_col}을 찾을 수 없습니다.'}, status=404)
        
        # 디버깅: 전체 데이터 현황 출력
        total_records = len(anomaly_df)
        print(f"검색 API - 전체 이상치 레코드 수: {total_records}")
        print(f"검색 API - 검색 대상 사용자: '{username}', 컬럼: {user_col}")
        
        # 사용자명으로 검색 (정확 일치)
        exact_match = anomaly_df[anomaly_df[user_col].astype(str) == username]
        if exact_match.empty:
            return JsonResponse({'error': '정확한 사용자명을 입력해주세요.'}, status=404)
        
        # a: 해당 사용자의 이상 로그 수
        anomaly_count = int(len(exact_match))

        # b: 해당 사용자가 발생시킨 전체 로그 수 (원본 파일에서 조회)
        try:
            # 원본 CSV 파일에서 전체 로그 수 조회
            original_df = pd.read_csv(session.file_path)
            if user_col in original_df.columns:
                user_total_logs = int(original_df[original_df[user_col].astype(str) == username].shape[0])
            else:
                user_total_logs = 0
        except Exception:
            # 원본 파일 읽기 실패시 이상 로그 수로 대체
            user_total_logs = anomaly_count

        
        #정확히 일치하는 사용자가 있는지 확인
        count = int(len(exact_match))
        return JsonResponse({
            'username': username,
            'anomaly_count': anomaly_count, 
            'user_total_logs': user_total_logs, 
            'session_id': session.session_id
        })
        
        
    except AnalysisSession.DoesNotExist:
        return JsonResponse({'error': '분석 세션을 찾을 수 없습니다.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'검색 중 오류가 발생했습니다: {str(e)}'}, status=500)



from django.shortcuts import render


def anomaly_search_view(request):
    """
    사용자별 이상 로그 View All 페이지
    session_id가 제공되면 해당 세션의 데이터를 사용하고, 없으면 최신 세션 사용
    """
    session_id = request.GET.get('session_id')
    
    try:
        if session_id:
            # 특정 세션 조회
            session = AnalysisSession.objects.filter(session_id=session_id).first()
        else:
            # 최신 세션 조회
            session = AnalysisSession.objects.filter(
                user_graph_html__isnull=False
            ).order_by('-created_at').first()
        
        if not session:
            return render(request, 'web/viewall.html', {
                'error': '표시할 분석 결과가 없습니다.'
            })
        
        return render(request, 'web/viewall.html', {
            'session': session
        })
        
    except Exception as e:
        return render(request, 'web/viewall.html', {
            'error': f'데이터를 불러오는 중 오류가 발생했습니다: {str(e)}'
        })



@require_http_methods(["GET"])
def get_user_graph(request):
    """
    사용자별 이상 로그 그래프를 반환하는 뷰 (viewall.html용)
    session_id가 제공되면 해당 세션의 데이터를 사용하고, 없으면 최신 세션 사용
    show_more 파라미터로 더보기 기능 지원
    """
    session_id = request.GET.get('session_id')
    show_more = request.GET.get('show_more', 'false').lower() == 'true'
    
    try:
        if session_id:
            # 특정 세션 조회
            session = AnalysisSession.objects.filter(
                session_id=session_id,
                user_graph_html__isnull=False
            ).first()
        else:
            # 최신 세션 조회
            session = AnalysisSession.objects.filter(
                user_graph_html__isnull=False
            ).order_by('-created_at').first()
        
        # viewall 페이지에서는 새로 그래프 생성 (기본 10명, 더보기 시 더 많이)
        if session:
            print(f"viewall 그래프 생성 중... (session: {session.session_id}, show_more: {show_more})")
            
            # 세션의 데이터를 다시 로드하여 그래프 생성
            from .ai.visualize_graph import plot_anomaly_by_user
            import pandas as pd
            import json
            
            # 세션에서 데이터 가져오기 (검색 API와 동일한 소스 사용)
            if hasattr(session, 'analysis_result') and session.analysis_result:
                try:
                    # analysis_result에서 이상치 데이터 가져오기 (검색 API와 동일)
                    anomaly_records = session.analysis_result.get('records', [])
                    user_col = session.user_col or 'user'
                    
                    if anomaly_records:
                        # DataFrame으로 변환
                        df_anomaly = pd.DataFrame(anomaly_records)
                        
                        # 디버깅: EMP0111 사용자의 실제 데이터 개수 출력
                        if user_col in df_anomaly.columns:
                            emp0111_count = len(df_anomaly[df_anomaly[user_col].astype(str).str.strip() == 'EMP0111'])
                            total_anomaly_count = len(df_anomaly)
                            print(f"그래프 생성용 데이터에서 EMP0111의 이상치 개수: {emp0111_count} / 전체 이상치: {total_anomaly_count}")
                        
                        # viewall용 그래프 생성 (기본 10명, 더보기 시 더 많이)  
                        user_graph_html = plot_anomaly_by_user(df_anomaly, user_col, top_n=10, show_more=show_more, for_dashboard=False)
                        
                        if user_graph_html:
                            return HttpResponse(user_graph_html)
                except Exception as e:
                    print(f"viewall 그래프 생성 실패: {e}")
                    # 실패시 기본 그래프 사용
        
        if session and session.user_graph_html:
            user_graph_html = session.user_graph_html

            # 그래프 시각 요소 조정 스크립트
            size_adjustment_script = """
            <script>
            document.addEventListener('DOMContentLoaded', function() {
                setTimeout(function() {
                    try {
                        var plotElement = document.querySelector('.plotly-graph-div');
                        if (plotElement && window.Plotly) {
                            var currentLayout = plotElement.layout || {};
                            
                            var newLayout = {
                                ...currentLayout,
                                height: 600,
                                font: {size: 16},
                                margin: {l: 60, r: 60, t: 80, b: 80},
                                title: {
                                    text: currentLayout.title?.text || 'Anomalies by User',
                                    font: {size: 20}
                                },
                                xaxis: {
                                    ...currentLayout.xaxis,
                                    showticklabels: true,
                                    tickangle: 45,
                                    tickfont: {size: 10}
                                }
                            };
                            
                            Plotly.relayout(plotElement, newLayout);
                        }
                    } catch (e) {
                    }
                }, 500);
            });
            </script>
            """

            return HttpResponse(user_graph_html + size_adjustment_script)

        # user_graph_html이 없으면 아무것도 출력하지 않음
        return HttpResponse("")
    
    except Exception as e:
        print(f"get_user_graph 오류: {e}")
        return HttpResponse(f"""
            <div style="display: flex; align-items: center; justify-content: center; height: 400px; color: #dc3545;">
                <div style="text-align: center;">
                    <h3>그래프 로딩 오류</h3>
                    <p>그래프를 불러오는 중 오류가 발생했습니다.</p>
                    <small>{str(e)}</small>
                    <br><br>
                    <a href="/dashboard/" style="color: #007bff; text-decoration: none;">
                        대시보드로 돌아가기 →
                    </a>
                </div>
            </div>
        """)


def total_anomaly_count(request):
    """
    전체 이상 로그 건수를 반환합니다.
    """
    session_id = request.GET.get('session_id')
    
    try:
        # session_id가 제공된 경우 해당 세션에서 조회, 없으면 최신 세션 사용
        if session_id:
            session = AnalysisSession.objects.get(session_id=session_id)
        else:
            session = AnalysisSession.objects.filter(
                user_col__isnull=False
            ).order_by('-created_at').first()
        
        if not session:
            return JsonResponse({'error': '분석 세션이 없습니다.'}, status=404)
        
        # 세션의 analysis_result에서 데이터 조회
        if session.analysis_result:
            anomaly_count = session.analysis_result.get('anomaly_count', 0)
            total_count = session.analysis_result.get('total', 0)
            summary = session.analysis_result.get('summary', f'이상치 {anomaly_count:,}건 / 전체 {total_count:,}건')
            
            return JsonResponse({
                'total_count': anomaly_count,  # 이상치 건수 (기존 API와 호환성 유지)
                'anomaly_count': anomaly_count,
                'total': total_count,
                'summary': summary
            })
        else:
            return JsonResponse({'error': '분석 결과가 없습니다.'}, status=404)
        
    except AnalysisSession.DoesNotExist:
        return JsonResponse({'error': '분석 세션을 찾을 수 없습니다.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'조회 중 오류가 발생했습니다: {str(e)}'}, status=500)
    
from django.shortcuts import render
from .models import AnalysisSession
import pandas as pd
from .ai.visualize_graph import plot_anomaly_by_hour

@require_http_methods(["GET"])
def anomaly_by_hour_viewall(request):
    """
    시간대별 이상 로그 View All 페이지
    session_id가 제공되면 해당 세션의 데이터를 사용하고, 없으면 최신 세션 사용
    """
    session_id = request.GET.get('session_id')
    
    try:
        if session_id:
            # 특정 세션 조회
            session = AnalysisSession.objects.filter(session_id=session_id).first()
        else:
            # 최신 세션 조회
            session = AnalysisSession.objects.filter(
                hour_graph_html_top10__isnull=False
            ).order_by('-created_at').first()
        
        if not session:
            return render(request, 'web/anomaly_by_hour.html', {
                'hour_graph_html': "<p>시간별 이상 탐지 그래프가 없습니다.</p>"
            })
        
        # top10 버전이 있으면 사용하고, 없으면 top3 버전 사용
        hour_graph_html = session.hour_graph_html_top10 or session.hour_graph_html_top3
        
        return render(request, 'web/anomaly_by_hour.html', {
            'hour_graph_html': hour_graph_html,
            'session': session
        })
        
    except Exception as e:
        return render(request, 'web/anomaly_by_hour.html', {
            'hour_graph_html': f"<p>그래프 로딩 중 오류 발생: {str(e)}</p>"
        })

def generate_interactive_summary_html(session):
    """분석 결과를 기반으로 인터랙티브 요약 HTML 생성 - 가로 누적막대 버전"""
    if not session.analysis_result:
        return "<p>분석 결과가 없습니다.</p>"
    
    try:
        time_periods, top_users = parse_analysis_data(session)
        
        max_time_period = max(time_periods, key=lambda x: x['count']) if time_periods else None
        max_user = max(top_users, key=lambda x: x['count']) if top_users else None
        
        total_time_anomalies = sum(p['count'] for p in time_periods)
        total_user_anomalies = sum(u['count'] for u in top_users)
        
        time_segments = []
        if total_time_anomalies > 0:
            cumulative = 0
            for period in time_periods:
                percentage = (period['count'] / total_time_anomalies) * 100
                time_segments.append({
                    'period': period['period'],
                    'count': period['count'],
                    'percentage': percentage,
                    'color': period['color'],
                    'start': cumulative,
                    'width': percentage
                })
                cumulative += percentage
        
        user_segments = []
        if total_user_anomalies > 0:
            cumulative = 0
            for user in top_users:
                percentage = (user['count'] / total_user_anomalies) * 100
                user_segments.append({
                    'user': user['user'],
                    'count': user['count'],
                    'percentage': percentage,
                    'color': user['color'],
                    'start': cumulative,
                    'width': percentage
                })
                cumulative += percentage
        
        html = f"""
        <div style="display: flex; gap: 2rem; height: 100%;">
            <div style="flex: 1; padding: 1rem;">
                <h4 style="color: #1976d2; margin-bottom: 1rem; border-bottom: 2px solid #e3f2fd; padding-bottom: 0.5rem;">종합 평가</h4>
                
                <div style="margin-bottom: 2rem;">
                    <h5 style="color: #333; margin-bottom: 1rem;"><p style="font-size:1"><b>시간대별 이상 로그 분포 (총 {total_time_anomalies}건)</b></p></h5>
                    <div style="height: 120px; margin-bottom: 1rem; border: 1px solid #eee; border-radius: 8px; padding: 20px; display: flex; flex-direction: column; gap: 15px; justify-content: center;">
                        <div style="position: relative; width: 100%; height: 50px; background: #f5f5f5; border-radius: 8px; overflow: hidden; display: flex;">
                            {"".join([
                                f'''<div 
                                    data-name="{seg['period']}"
                                    data-count="{seg['count']}"
                                    data-percentage="{seg['percentage']:.1f}"
                                    style="
                                        width: {seg['width']}%;
                                        background: {seg['color']};
                                        display: flex;
                                        align-items: center;
                                        justify-content: center;
                                        color: #000;
                                        font-size: 16px;
                                        font-weight: bold;
                                        cursor: pointer;
                                        transition: opacity 0.2s;
                                        position: relative;
                                    "
                                    onmouseover="this.style.opacity='0.8'; showBarTooltip(event, this)"
                                    onmouseout="this.style.opacity='1'; hideBarTooltip()"
                                    onmousemove="showBarTooltip(event, this)"
                                >
                                    {seg['count'] if seg['width'] > 8 else ''}
                                </div>'''
                                for seg in time_segments
                            ])}
                        </div>
                        <div style="display: flex; flex-wrap: wrap; gap: 12px; justify-content: center;">
                            {"".join([
                                f'<div style="display: flex; align-items: center; gap: 6px; font-size: 13px;"><div style="width: 14px; height: 14px; background: {seg["color"]}; border-radius: 3px;"></div><span>{seg["period"]} ({seg["count"]}건)</span></div>'
                                for seg in time_segments
                            ])}
                        </div>
                    </div>
                    <p style="color: #666; font-size: 0.95rem; line-height: 1.5; text-align: left;">
                        <b>{f'<span style="color: {max_time_period["color"]}; font-weight: bold;">{max_time_period["period"]}</span>에 가장 많은 이상 로그({max_time_period["count"]}건)가 집중되어 있습니다.' if max_time_period and max_time_period['count'] > 0 else '시간대별 이상 로그가 없거나 고르게 분포되어 있습니다.'}</b>
                    </p>
                </div>
                
                <div>
                    <h5 style="color: #333; margin-bottom: 1rem;"><p style="font-size:1"><b>상위 사용자 이상 로그 개수 (총 {total_user_anomalies}건)</b></p></h5>
                    <div style="height: 120px; margin-bottom: 1rem; border: 1px solid #eee; border-radius: 8px; padding: 20px; display: flex; flex-direction: column; gap: 15px; justify-content: center;">
                        <div style="position: relative; width: 100%; height: 50px; background: #f5f5f5; border-radius: 8px; overflow: hidden; display: flex;">
                            {"".join([
                                f'''<div 
                                    data-name="{seg['user']}"
                                    data-count="{seg['count']}"
                                    data-percentage="{seg['percentage']:.1f}"
                                    style="
                                        width: {seg['width']}%;
                                        background: {seg['color']};
                                        display: flex;
                                        align-items: center;
                                        justify-content: center;
                                        color: #000;
                                        font-size: 16px;
                                        font-weight: bold;
                                        cursor: pointer;
                                        transition: opacity 0.2s;
                                        position: relative;
                                    "
                                    onmouseover="this.style.opacity='0.8'; showBarTooltip(event, this)"
                                    onmouseout="this.style.opacity='1'; hideBarTooltip()"
                                    onmousemove="showBarTooltip(event, this)"
                                >
                                    {seg['count'] if seg['width'] > 8 else ''}
                                </div>'''
                                for seg in user_segments
                            ])}
                        </div>
                        <div style="display: flex; flex-wrap: wrap; gap: 12px; justify-content: center;">
                            {"".join([
                                f'<div style="display: flex; align-items: center; gap: 6px; font-size: 13px;"><div style="width: 14px; height: 14px; background: {seg["color"]}; border-radius: 3px;"></div><span>{seg["user"]} ({seg["count"]}건)</span></div>'
                                for seg in user_segments
                            ])}
                        </div>
                    </div>
                    <p style="color: #666; font-size: 0.95rem; line-height: 1.5; text-align: left;">
                        <b>{f'사용자 <span style="color: {max_user["color"]}; font-weight: bold;">{max_user["user"]}</span>에게 가장 많은 이상 로그({max_user["count"]}건)가 집중되어 있습니다.' if max_user and max_user['count'] > 0 else '사용자별 이상 로그 분포를 확인할 수 없습니다.'}</b>
                    </p>
                    <br>
                </div>
            </div>
        </div>
        
        <div id="bar-tooltip" style="
            position: fixed;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            opacity: 0;
            z-index: 10000;
            transition: opacity 0.2s;
        "></div>
        
        <script type="text/javascript">
            function showBarTooltip(event, element) {{
                const tooltip = document.getElementById('bar-tooltip');
                const name = element.getAttribute('data-name');
                const count = element.getAttribute('data-count');
                const percentage = element.getAttribute('data-percentage');
                
                tooltip.innerHTML = `<strong>${{name}}</strong><br/>이상 로그: ${{count}}건<br/>비율: ${{percentage}}%`;
                tooltip.style.left = (event.pageX + 10) + 'px';
                tooltip.style.top = (event.pageY - 28) + 'px';
                tooltip.style.opacity = '1';
            }}
            
            function hideBarTooltip() {{
                const tooltip = document.getElementById('bar-tooltip');
                tooltip.style.opacity = '0';
            }}
        </script>
        """
        
        return html
    except Exception as e:
        print(f"DEBUG: generate_interactive_summary_html 오류: {e}")
        import traceback
        traceback.print_exc()
        return f"<p>종합 설명 생성 중 오류가 발생했습니다: {str(e)}</p>"

def parse_analysis_data(session):
    """분석 결과에서 실제 데이터를 파싱하여 차트 데이터 생성 (디버깅 강화)"""
    time_periods = []
    top_users = []
    
    try:
        print(f"DEBUG: parse_analysis_data 시작, session.id={session.id}")
        
        if session.analysis_result and 'result_csv_path' in session.analysis_result:
            csv_path = session.analysis_result['result_csv_path']
            print(f"DEBUG: CSV 경로: {csv_path}")
            
            if not os.path.exists(csv_path):
                print(f"DEBUG: CSV 파일이 존재하지 않음: {csv_path}")
                raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {csv_path}")
                
            df = pd.read_csv(csv_path)
            print(f"DEBUG: CSV 로드 성공, shape={df.shape}")
            print(f"DEBUG: 컬럼명: {list(df.columns)}")
            
            anomaly_df = df[df['Anomaly'] == 1]
            print(f"DEBUG: 이상치 데이터 shape={anomaly_df.shape}")
            
            if not anomaly_df.empty and session.time_col and session.time_col in anomaly_df.columns:
                print(f"DEBUG: 시간 컬럼 '{session.time_col}' 처리 시작")
                
                try:
                    anomaly_df = anomaly_df.copy()  
                    anomaly_df[session.time_col] = pd.to_datetime(anomaly_df[session.time_col])
                    anomaly_df['hour'] = anomaly_df[session.time_col].dt.hour
                    
                    print(f"DEBUG: 시간대별 분포: {anomaly_df['hour'].value_counts().sort_index()}")
                    
                    def categorize_time(hour):
                        if 0 <= hour <= 5:
                            return '새벽시간(00-05시)'
                        elif 6 <= hour <= 11:
                            return '오전시간(06-11시)'
                        elif 12 <= hour <= 17:
                            return '오후시간(12-17시)'
                        else:
                            return '저녁시간(18-23시)'
                    
                    anomaly_df['time_period'] = anomaly_df['hour'].apply(categorize_time)
                    
                    time_counts = anomaly_df['time_period'].value_counts()
                    print(f"DEBUG: 시간대별 집계: {time_counts}")
                    
                    sorted_time_data = []
                    colors = ['#FF6B6B', '#4ECDC4', "#45B7D1", '#96CEB4']
                    periods = ['새벽시간(00-05시)', '오전시간(06-11시)', '오후시간(12-17시)', '저녁시간(18-23시)']
                    
                    period_data = []
                    for period in periods:
                        count = time_counts.get(period, 0)
                        period_data.append({
                            'period': period,
                            'count': int(count)
                        })
                    
                    period_data.sort(key=lambda x: x['count'], reverse=True)
                    
                    for i, data in enumerate(period_data):
                        time_periods.append({
                            'period': data['period'],
                            'count': data['count'],
                            'color': colors[i] if i < len(colors) else '#D3D3D3'
                        })
                        
                    print(f"DEBUG: time_periods 생성 완료 (시계방향 내림차순): {time_periods}")
                        
                except Exception as time_error:
                    print(f"DEBUG: 시간 컬럼 파싱 오류: {time_error}")
                    pass
            else:
                print(f"DEBUG: 시간 데이터 처리 건너뛰기 - empty={anomaly_df.empty}, time_col={session.time_col}")
            
            if not anomaly_df.empty and session.user_col and session.user_col in anomaly_df.columns:
                print(f"DEBUG: 사용자 컬럼 '{session.user_col}' 처리 시작")
                
                user_counts = anomaly_df[session.user_col].value_counts().head(4)
                print(f"DEBUG: 사용자별 집계: {user_counts}")
                
                colors = ['#FF6B6B', '#4ECDC4', "#45B7D1", '#96CEB4']
                
                for i, (user, count) in enumerate(user_counts.items()):
                    top_users.append({
                        'user': str(user)[:10],  
                        'count': int(count),
                        'color': colors[i] if i < len(colors) else '#D3D3D3'
                    })
                
                if len(user_counts) > 4:
                    other_count = user_counts.iloc[4:].sum()
                    if other_count > 0:
                        top_users.append({
                            'user': '기타',
                            'count': int(other_count),
                            'color': '#D3D3D3'
                        })
                
                print(f"DEBUG: top_users 생성 완료: {top_users}")
            else:
                print(f"DEBUG: 사용자 데이터 처리 건너뛰기 - empty={anomaly_df.empty}, user_col={session.user_col}")
                    
    except Exception as e:
        print(f"DEBUG: 데이터 파싱 오류: {e}")
        import traceback
        traceback.print_exc()
    
    if not time_periods:
        print("DEBUG: time_periods가 비어있음, 기본값 설정")
        time_periods = [
            {'period': '새벽시간(00-05시)', 'count': 0, 'color': '#FF6B6B'},
            {'period': '오전시간(06-11시)', 'count': 0, 'color': '#4ECDC4'},
            {'period': '오후시간(12-17시)', 'count': 0, 'color': "#45B7D1"},
            {'period': '저녁시간(18-23시)', 'count': 0, 'color': '#96CEB4'}
        ]
    
    if not top_users:
        print("DEBUG: top_users가 비어있음, 기본값 설정")
        top_users = [
            {'user': '데이터 없음', 'count': 0, 'color': '#D3D3D3'}
        ]
    
    print(f"DEBUG: parse_analysis_data 완료 - time_periods={len(time_periods)}, top_users={len(top_users)}")
    return time_periods, top_users

