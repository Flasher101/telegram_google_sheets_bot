import pandas as pd

def create_activity_chart(df, date_from, date_to):
    """График активности по дням"""
    if 'timestamp' not in df.columns:
        return pd.DataFrame()

    df_filtered = df[
        (df['timestamp'].dt.date >= date_from) &
        (df['timestamp'].dt.date <= date_to)
    ]

    # Группировка по дням
    daily_counts = df_filtered.groupby(df_filtered['timestamp'].dt.date).size()
    return daily_counts

def create_response_time_chart(df, date_from, date_to):
    """График времени ответа"""
    if 'response_time' not in df.columns or 'timestamp' not in df.columns:
        return pd.DataFrame()

    df_filtered = df[
        (df['timestamp'].dt.date >= date_from) &
        (df['timestamp'].dt.date <= date_to)
    ]

    # Среднее время ответа по дням
    daily_response = df_filtered.groupby(df_filtered['timestamp'].dt.date)['response_time'].mean()
    return daily_response
