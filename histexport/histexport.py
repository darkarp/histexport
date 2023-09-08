import os
import sqlite3
import logging
import argparse
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Any, Union


def init_logging(enable_logging: bool) -> None:
    """Initialize logging.

    Args:
        enable_logging (bool): Flag to enable or disable logging.
    """
    if enable_logging:
        logging.basicConfig(level=logging.INFO)
        logging.info("Logging is enabled.")


def connect_db(path_to_history: str) -> Optional[sqlite3.Connection]:
    """Connect to an SQLite database.

    Args:
        path_to_history (str): Path to SQLite database.

    Returns:
        sqlite3.Connection: SQLite connection object if successful, None otherwise.
    """
    try:
        conn = sqlite3.connect(path_to_history)
        logging.info(f"Connected to SQLite database at {path_to_history}")
        return conn
    except Exception as e:
        logging.error(str(e))
        return None


def fetch_and_write_data(
        conn: sqlite3.Connection, output_dir: str, output_base: str, formats: List[str],
        extract_types: List[str]) -> None:
    """Fetch data from the SQLite database and write it to specified output formats.

    Args:
        conn (sqlite3.Connection): SQLite connection object.
        output_dir (str): Directory where the output will be saved.
        output_base (str): Base name for the output files.
        formats (List[str]): List of output formats (csv, xlsx, txt).
        extract_types (List[str]): List of data types to extract (urls, downloads).
    """
    cursor = conn.cursor()
    epoch_start = datetime(1601, 1, 1)

    def convert_chrome_time(chrome_time):
        return epoch_start + timedelta(microseconds=chrome_time)

    def fetch_and_convert_data(query, columns, time_cols):
        cursor.execute(query)
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=columns)
        for time_col in time_cols:
            if time_col in df.columns:
                df[time_col] = df[time_col].apply(convert_chrome_time)
        return df

    query_dict = {
        'urls': ("SELECT url, title, visit_count, last_visit_time FROM urls", ['URL', 'Title', 'Visit_Count', 'Last_Visit_Time'], ['Last_Visit_Time']),
        'downloads': ("SELECT downloads.target_path, downloads.start_time, downloads.end_time, downloads.total_bytes, downloads.received_bytes, downloads_url_chains.url FROM downloads INNER JOIN downloads_url_chains ON downloads.id=downloads_url_chains.id",
                      ['Target_Path', 'Start_Time', 'End_Time', 'Total_Bytes', 'Received_Bytes', 'URL'], ['Start_Time', 'End_Time'])
    }

    def _pretty_txt(df, file_name):
        longest_field_name = max(df.columns, key=len)
        field_name_length = len(longest_field_name)

        max_length = max(
            len(f"{field}: {value}")
            for _, row in df.iterrows()
            for field, value in zip(df.columns, row)
        )

        with open(file_name, 'w', encoding='utf-8') as f:
            for _, row in df.iterrows():
                for field, value in zip(df.columns, row):
                    f.write(f"{field.ljust(field_name_length)}: {value}\n")
                f.write("=" * max_length + "\n")

    for extract_type in extract_types:
        query, columns, time_cols = query_dict[extract_type]
        df = fetch_and_convert_data(query, columns, time_cols)
        for fmt in formats:
            output_file = os.path.join(
                output_dir, f"{output_base}_{extract_type}.{fmt}")
            if fmt == 'csv':
                df.to_csv(output_file, index=False)
            elif fmt == 'xlsx':
                df.to_excel(output_file, index=False, engine='openpyxl')
            elif fmt == 'txt':
                _pretty_txt(df, output_file)
            logging.info(f"Data saved to {output_file}")


def is_sqlite3(filename: str) -> bool:
    """Check if a file is an SQLite3 database.

    Args:
        filename (str): File path to check.

    Returns:
        bool: True if the file is an SQLite3 database, False otherwise.
    """
    with open(filename, 'rb') as f:
        header = f.read(16)
    return header == b'SQLite format 3\x00'


def main():
    """Main function to run the application. Parses command line arguments and
    orchestrates the extraction and writing of data.

    Returns:
        int: Exit code (0 for success, non-zero for failure).
    """
    parser = argparse.ArgumentParser(
        description="Export Chromium-based browser and download history to various formats.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Examples:
        1) Basic extraction of URLs and Downloads in `txt`:
            histexport -i path/to/history/history_file -o output_file
        2) Specify output directory and formats:
            histexport -i path/to/history/history_file -o output_file -d path/to/output -f csv xlsx
        3) Enable logging (`-l`):
            histexport -i path/to/history/history_file -o output_file -l
        4) Extract URLs and downloads from a folder of SQLite files:
            histexport -i path/to/history_folder -t folder -o output_file -d path/to/output -f csv xlsx -e urls downloads
        """)
    parser.add_argument('-i', '--input', required=True,
                        help='Path to the SQLite history file.')
    parser.add_argument('-t', '--type', choices=['file', 'folder'], default='file',
                        help='Type of the input: file or folder. Default is file')
    parser.add_argument('-o', '--output', required=True,
                        help='Base name for the output files.')
    parser.add_argument('-d', '--dir', required=False, default='./',
                        help='Output directory. Default is current directory')
    parser.add_argument(
        '-f', '--formats', nargs='+', choices=['csv', 'xlsx', 'txt'], default=['txt'],
        help='Output formats. Multiple formats can be specified. Default is txt')
    parser.add_argument('-e', '--extract', nargs='+', choices=['urls', 'downloads'], default=[
                        'urls', 'downloads'], help='Types to extract: urls, downloads, or both. Default is both')
    parser.add_argument('-l', '--log', action='store_true',
                        help='Enable logging. Default is disabled')

    args = parser.parse_args()

    # Initialize logging if enabled
    init_logging(args.log)

    # Validate and create output directory
    if not os.path.exists(args.dir):
        os.makedirs(args.dir)

    def _process_history_file(input_path, output_dir, output_base, formats, extract_types):
        conn = connect_db(input_path)
        fetch_and_write_data(conn, output_dir, output_base, formats, extract_types)

    exit_code = 0  # EXIT_SUCCESS
    try:
        if args.type == 'folder':
            # Process all SQLite3 files in the directory
            for filename in os.listdir(args.input):
                input_path = os.path.join(args.input, filename)
                if is_sqlite3(input_path):
                    output_base = os.path.splitext(filename)[0]
                    _process_history_file(input_path, args.dir, output_base, args.formats, args.extract)
        else:
            # Process single SQLite3 file
            conn = connect_db(args.input)
            if conn is None:
                exit_code = 1  # EXIT_FAILURE
            else:
                _process_history_file(conn, args.dir, args.output, args.formats, args.extract)
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        exit_code = 2

    return exit_code


if __name__ == "__main__":
    exit(main())
