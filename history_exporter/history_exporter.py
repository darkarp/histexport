import sqlite3
import pandas as pd
import argparse
import logging
from datetime import datetime, timedelta


def init_logging(enable_logging):
    if enable_logging:
        logging.basicConfig(level=logging.INFO)
        logging.info("Logging is enabled.")


def connect_db(path_to_history):
    try:
        conn = sqlite3.connect(path_to_history)
        logging.info(f"Connected to SQLite database at {path_to_history}")
        return conn
    except Exception as e:
        logging.error(str(e))
        exit(1)


def pretty_txt(df, file_name):
    # Find the longest field name to properly align all field names
    longest_field_name = max(df.columns, key=len)
    field_name_length = len(longest_field_name)

    # Calculate the length of the longest value to align all '='
    max_length = 0
    for _, row in df.iterrows():
        for field, value in zip(df.columns, row):
            length = len(f"{field}: {value}")
            if length > max_length:
                max_length = length

    with open(file_name, 'w', encoding='utf-8') as f:
        for _, row in df.iterrows():
            for field, value in zip(df.columns, row):
                # Left-align the field names and right-align the values
                f.write(f"{field.ljust(field_name_length)}: {value}\n")
            f.write("=" * max_length + "\n")


def fetch_and_write_data(conn, output_base, formats, extract_types):
    cursor = conn.cursor()
    epoch_start = datetime(1601, 1, 1)

    def convert_chrome_time(chrome_time):
        return epoch_start + timedelta(microseconds=chrome_time)

    def fetch_and_convert_data(conn, query, columns, time_cols):
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=columns)
        for time_col in time_cols:
            if time_col in df.columns:
                df[time_col] = df[time_col].apply(convert_chrome_time)
        return df

    query_dict = {
        'urls': ("SELECT url, title, visit_count, last_visit_time FROM urls", ['URL', 'Title', 'Visit_Count', 'Last_Visit_Time'], ['Last_Visit_Time']),
        'downloads': ("""SELECT downloads.target_path, downloads.start_time, downloads.end_time, downloads.total_bytes, downloads.received_bytes, downloads_url_chains.url FROM downloads INNER JOIN downloads_url_chains ON downloads.id=downloads_url_chains.id""",
                      ['Target_Path', 'Start_Time', 'End_Time', 'Total_Bytes', 'Received_Bytes', 'URL'], ['Start_Time', 'End_Time'])
    }

    for extract_type in extract_types:
        query, columns, time_cols = query_dict[extract_type]
        df = fetch_and_convert_data(conn, query, columns, time_cols)
        for fmt in formats:
            output_file = f"{output_base}_{extract_type}.{fmt}"
            if fmt == 'csv':
                df.to_csv(output_file, index=False)
            elif fmt == 'xlsx':
                df.to_excel(output_file, index=False, engine='openpyxl')
            elif fmt == 'txt':
                pretty_txt(df, output_file)
            logging.info(f"Data saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Export Chromium-based browser and download history to various formats.")
    parser.add_argument('-i', '--input', required=True,
                        help='Path to the SQLite history file.')
    parser.add_argument('-o', '--output', required=True,
                        help='Base name for the output files.')
    parser.add_argument(
        '-f', '--formats', nargs='+', choices=['csv', 'xlsx', 'txt'],
        default=['csv'],
        help='Output formats. Multiple formats can be specified.')
    parser.add_argument('-e', '--extract', nargs='+', choices=['urls', 'downloads'], default=[
                        'urls', 'downloads'], help='Types to extract: urls, downloads, or both.')
    parser.add_argument('-l', '--log', action='store_true',
                        help='Enable logging.')

    args = parser.parse_args()
    init_logging(args.log)

    conn = connect_db(args.input)
    fetch_and_write_data(conn, args.output, args.formats, args.extract)


if __name__ == "__main__":
    main()
