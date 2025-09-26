# restore.py

import pandas as pd

def generate_reverse_mappings(encoder_mapping_dict):
    reverse_mappings = {}
    for col, mapping_df in encoder_mapping_dict.items():
        mapping_df_reset = mapping_df.reset_index()
        original_vals = mapping_df_reset[mapping_df_reset.columns[0]]
        encoded_vals = mapping_df_reset[col]
        reverse_mappings[col] = dict(zip(encoded_vals, original_vals))
    return reverse_mappings

def restore_encoded_columns(df_encoded, reverse_mappings):
    df_restored = df_encoded.copy()
    for col, reverse_map in reverse_mappings.items():
        if col in df_restored.columns:
            # 문자로만 복원
            df_restored[col] = df_restored[col].map(reverse_map).fillna(df_restored[col])
    return df_restored

def restore_and_save_readable_anomalies(anomaly_csv_path, encoder_mapping_dict, output_path):
    df = pd.read_csv(anomaly_csv_path)

    # 역매핑 생성
    reverse_mappings = generate_reverse_mappings(encoder_mapping_dict)

    # 문자열 컬럼만 복원 (숫자형은 그대로 둠)
    df_restored = restore_encoded_columns(df, reverse_mappings)

    # 저장
    df_restored.to_csv(output_path, index=False)
    print(f"사람이 읽을 수 있는 이상치 결과 {len(df_restored)}건이 '{output_path}'에 저장되었습니다.")
    return df_restored