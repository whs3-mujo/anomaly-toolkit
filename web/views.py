from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from .forms import UploadFileForm
from .models import AnalysisSession, AnomalyLog
import uuid
import json
import os
from django.conf import settings
import pandas as pd
from .ai_script import detect_anomalies
from .visualize_graph import plot_anomaly_by_hour, plot_anomaly_by_user, plot_anomaly_score_distribution
from django.db.models import Count, Q
from django.contrib.auth.models import User
import time
import threading

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
        return JsonResponse({
            'success': True,
            'session': {
                'id': session.id,
                'session_id': session.session_id,
                'filename': session.original_filename,
                'file_type': session.file_type,
                'created_at': session.created_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'analysis_result': session.analysis_result,
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
    """분석 세션 삭제"""
    try:
        session = get_object_or_404(AnalysisSession, session_id=session_id)
        session.delete()
        return JsonResponse({'success': True, 'message': '분석 기록이 삭제되었습니다.'})
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
                print(f"파일 저장 완료: {save_path}")

                analysis_result = detect_anomalies(save_path)
                print(f"분석 결과: {analysis_result}")

                # 업로드만 하는 경우에는 그래프 저장하지 않음
                AnalysisSession.objects.create(
                    session_id=str(uuid.uuid4()),
                    original_filename=file.name,
                    file_path=save_path,
                    file_type=os.path.splitext(file.name)[-1][1:].upper(),
                    analysis_result=analysis_result,
                )
                print("DB 저장 완료")
                return redirect("web:dashboard")
            except Exception as e:
                print(f"업로드 중 오류: {e}")
                return render(request, "web/upload.html", {"form": form, "error": str(e)})
        else:
            print("폼이 유효하지 않음:", form.errors)
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
                    print(f"인코딩 {enc} 시도 중 오류: {e}")
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
            
            # 빈 문자열을 None으로 변환
            user_col = user_col if user_col else None
            time_col = time_col if time_col else None
            file_path = save_uploaded_file(file)
            result = detect_anomalies(file_path, exclude_columns, user_col=user_col, time_col=time_col)
            result_csv_path = result.get("result_csv_path")
            df_result = pd.read_csv(result_csv_path)

            # 타임아웃 설정 (10분)
            timeout = 600  # 초 단위
            
            # 결과 변수 및 에러 플래그
            result = None
            analysis_error = False
            
            def run_analysis():
                nonlocal result, analysis_error
                try:
                    result = detect_anomalies(file_path, exclude_columns, user_col=user_col, time_col=time_col)
                except Exception as e:
                    analysis_error = True
                    print(f"분석 중 오류 발생: {e}")
            
            # 분석 쓰레드 시작
            analysis_thread = threading.Thread(target=run_analysis)
            analysis_thread.start()
            
            # 지정된 시간만큼 대기
            analysis_thread.join(timeout)
            
            # 타임아웃 발생 시
            if analysis_thread.is_alive() or analysis_error:
                return JsonResponse({
                    'success': False, 
                    'error': '처리할 수 없는 데이터셋입니다. 10분 이상 소요되었습니다.'
                }, status=408)  # 408 Request Timeout

            # === 그래프 HTML 생성 및 저장 ===
            user_graph_html = plot_anomaly_by_user(df_result, user_col) if user_col and user_col in df_result.columns else None
            score_graph_html = plot_anomaly_score_distribution(df_result)
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
        records = result.get("all_records", [])
    else:
        records = result.get("records", [])

    if not records:
        return HttpResponse("다운로드할 데이터가 없습니다.", status=404)

    df = pd.DataFrame(records)
    # 한글 깨짐 방지: utf-8-sig로 저장
    csv_data = df.to_csv(index=False, encoding="utf-8-sig")
    # 파일명에서 .csv 중복 제거
    base_name = session.original_filename
    if base_name.lower().endswith('.csv'):
        base_name = base_name[:-4]
    filename = f"{base_name}_{'전체' if download_type == 'all' else '이상치'}.csv"
    response = HttpResponse(csv_data, content_type="text/csv; charset=utf-8-sig")
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def visualize_graph_view(request):
    if request.method == "POST":
        file = request.FILES["file"]
        user_col = request.POST.get("user_col")
        time_col = request.POST.get("time_col")
        file_path = save_uploaded_file(file)
        df = pd.read_csv(file_path)
        hour_html = plot_anomaly_by_hour(df, user_col, time_col)
        user_html = plot_anomaly_by_user(df, user_col)
        score_html = plot_anomaly_score_distribution(df)

        context = {
            'hour_graph': hour_html,
            'user_graph': user_html,
            'score_graph': score_html,
        }
        return render(request, 'web/dashboard.html', context)
    return JsonResponse({"error": "Invalid request"}, status=400)


#get_shap_plot 함수를 선언하여 SHAP그래프를 생성 및 이미지 파일 만듦. 그래프 모양, 크기를 여기서 바꿀 수 있음
import pandas as pd
import numpy as np
import shap
import matplotlib
import matplotlib.pyplot as plt
from django.http import JsonResponse
from io import BytesIO
import base64
from django.shortcuts import get_object_or_404
from .models import AnalysisSession
import platform

# 한글 폰트 설정 (윈도우 기준 예시)
matplotlib.rc('font', family='Malgun Gothic')  # 윈도우용
matplotlib.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지
matplotlib.use('Agg')

if platform.system() == 'Windows':
    matplotlib.rc('font', family='Malgun Gothic')
else:
    matplotlib.rc('font', family='AppleGothic')

def get_shap_plot(request, session_id, row_index):
    session = get_object_or_404(AnalysisSession, session_id=session_id)
    
    # 원본 데이터 로드 (실제 칼럼 확인용)
    try:
        original_df = pd.read_csv(session.file_path)
        original_columns = set(original_df.columns)
    except (FileNotFoundError, pd.errors.EmptyDataError, pd.errors.ParserError):
        original_df = None
        original_columns = set()
    
    # 데이터 불러오기
    X = pd.read_csv(session.file_path.replace(".csv", "_X_for_shap.csv"))
    shap_values = np.load(session.file_path.replace(".csv", "_shap_values.npy"))
    feature_cols = X.columns.tolist()
    
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
    fig, ax = plt.subplots(figsize=(6, max(8, max_len * 1.5)))


    # SHAP 값을 절댓값으로 바꿔 오른쪽으로 표시
    flipped_values = -negative_df['shap_value']  
    ax.set_xlim(0, flipped_values.max() * 1.2)

    ax.barh(y_pos, flipped_values, color='salmon', label='이상치 기여도', align='center', height = 0.5)
    ax.axvline(x=0, color='black', linewidth=1)

    ax.grid(axis='y', visible=False)  # 가로줄 제거
    ax.grid(axis='x', visible=True, linestyle='--', alpha=0.8)  # 세로줄은 표시 (옵션)


    ax.set_yticks(y_pos)
    ax.set_yticklabels([''] * max_len)
    ax.invert_yaxis()

    for i, label in enumerate(negative_df['feature']):
        if label:
            ax.text(flipped_values[i] + flipped_values.max() * 0.02, i, label, ha='left', va='center', fontsize=10, fontweight='bold')

    ax.set_title(f"{row_index}번 ROW\n", fontweight='bold')
    ax.set_xlabel("영향도 크기 (SHAP)")
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.1), frameon=False)

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.15)

    # base64 인코딩
    buffer = BytesIO()
    fig.savefig(buffer, format="png")
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    encoded = base64.b64encode(image_png).decode('utf-8')
    img_html = f'<img src="data:image/png;base64,{encoded}" style="width:100%;">'

    explanation_text = generate_shap_explanation(negative_df)  #SHAP 줄글 설명용

    # 그래프 아래 설명용 문단
    middle_html = """
    <div style='margin: 1rem 0; color: #666; font-size: 0.95em;'>
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
        'shap_explanation': explanation_text,
        'description_html': description_html 

})


#SHAP 그래프에 대한 줄글 설명 출력 코드
def generate_shap_explanation(shap_row_df):
    explanations = []
    for _, row in shap_row_df.iterrows():
        feature = row['feature']
        if not feature:  # feature가 비어 있는 경우 (빈 bar용) 설명 제외
            continue

        # SHAP 값의 절댓값을 기준으로 영향도 판단
        shap_magnitude = abs(row['shap_value'])
        data_value = row['data']
        
        # 만약 data_value가 Series나 배열이면 float로 변환 (대표값 사용)
        if isinstance(data_value, (np.ndarray, pd.Series)):
            data_magnitude = float(np.abs(data_value).max())
        else:
            data_magnitude = abs(float(data_value)) if data_value is not None else 0.0

        # SHAP 값의 크기에 따른 영향도 레벨 결정
        if shap_magnitude > 0.1:
            level = "<span style='color: #B22222'>크게</span>"  # 빨간색
        elif shap_magnitude > 0.05:
            level = "<span style='color: #e67e22'>중간 정도</span>"  # 주황색
        elif shap_magnitude > 0.01:
            level = "<span style='color: #f1c40f'>약간</span>"  # 노란색
        else:
            level = "거의"

        # 설명 텍스트 생성 - SHAP 기여도를 중심으로
        if shap_magnitude < 0.01:
            explanations.append(
                f"{feature}: 이상 탐지에 거의 영향 없음 (기여도: {shap_magnitude:.3f})"
            )
        else:
            # 데이터 차이와 영향도의 관계 설명
            if data_magnitude < 0.01 and shap_magnitude > 0.05:
                # 값 차이는 작지만 영향이 큰 경우
                explanation_reason = "※ 이 특성은 희귀하거나 모델이 중요하게 학습한 패턴입니다"
                data_text = "값의 차이는 미미하지만"
            elif data_magnitude < 0.01:
                data_text = "값의 차이는 미미하며"
                explanation_reason = ""
            elif data_magnitude < 1.0:
                data_text = f"평균 대비 {data_magnitude:.2f} 차이로"
                explanation_reason = ""
            else:
                data_text = f"평균 대비 {data_magnitude:.2f} 만큼 크게 차이나며"
                explanation_reason = ""
            
            base_explanation = f"{feature}: {data_text} 이상 탐지에 {level} 영향 (기여도: {shap_magnitude:.3f})"
            if explanation_reason:
                explanations.append(f"{base_explanation}<br><small style='color: #666; font-style: italic;'>{explanation_reason}</small>")
            else:
                explanations.append(base_explanation)

    explanations.append("<span style='color: #555; font-size: 0.95em;'>💡 <strong>참고:</strong> 값의 차이가 작아도 영향이 클 수 있습니다. 이는 해당 특성이 희귀하거나, 모델이 이상 탐지의 중요한 패턴으로 학습했기 때문입니다.</span>")

    return explanations

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_all_analysis_sessions(request):
    """모든 분석 세션 삭제"""
    AnalysisSession.objects.all().delete()
    return JsonResponse({"success": True})


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
    try:
        top_users = (
            AnomalyLog.objects.values('user__username')
            .annotate(count=Count('id'))
            .order_by('-count')[:top_n]
        )
        formatted_users = [{'username': user['user__username'], 'anomaly_count': user['count']} for user in top_users]
        return JsonResponse({'top_users': formatted_users})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["GET"])
def search_anomaly_logs(request):
    """
    특정 사용자의 이상 로그 건수를 검색합니다.
    """
    query = request.GET.get('username', '')  # GET 요청에서 'username' 파라미터 가져오기
    if query:
        # 먼저 해당 사용자가 실제로 존재하는지 확인
        try:
            user = User.objects.get(username=query)  # 정확한 사용자명으로 검색
            results = AnomalyLog.objects.filter(user=user)  # 해당 사용자의 이상 로그 검색
            count = results.count()  # 검색된 이상 로그 건수
            return JsonResponse({'username': query, 'anomaly_count': count})
        except User.DoesNotExist:
            return JsonResponse({'error': '정확한 사용자명을 입력해주세요.'}, status=404)
    else:
        return JsonResponse({'error': '검색어를 입력해주세요.'}, status=400)
from django.shortcuts import render


def anomaly_search_view(request):
    return render(request, 'web/viewall.html')



@require_http_methods(["GET"])
def get_user_graph(request):
    """
    사용자별 이상 로그 그래프를 반환하는 뷰 (viewall.html용)
    """
    try:
        latest_session = AnalysisSession.objects.filter(
            user_graph_html__isnull=False
        ).order_by('-created_at').first()
        
        if latest_session and latest_session.user_graph_html:
            user_graph_html = latest_session.user_graph_html

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
                                margin: {l: 60, r: 60, t: 80, b: 60},
                                title: {
                                    text: currentLayout.title?.text || 'Anomalies by User',
                                    font: {size: 20}
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
    try:
        total_count = AnomalyLog.objects.count()
        return JsonResponse({'total_count': total_count})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
from django.shortcuts import render
from .models import AnalysisSession
import pandas as pd
from .visualize_graph import plot_anomaly_by_hour

@require_http_methods(["GET"])
def anomaly_by_hour_viewall(request):
    """
    가장 최근 분석의 anomaly_by_hour 그래프 전체 화면 뷰어
    """
    try:
        latest_session = AnalysisSession.objects.filter(hour_graph_html_top10__isnull=False).order_by('-created_at').first()
        if latest_session is None:
            return render(request, 'web/anomaly_by_hour.html', {
                'hour_graph_html': "<p>시간별 이상 탐지 그래프가 없습니다.</p>"
            })
        
        return render(request, 'web/anomaly_by_hour.html', {
            'hour_graph_html': latest_session.hour_graph_html_top10
        })
    except Exception as e:
        return render(request, 'web/anomaly_by_hour.html', {
            'hour_graph_html': f"<p>그래프 로딩 중 오류 발생: {str(e)}</p>"
        })