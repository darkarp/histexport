import os
import shutil
import sqlite3
import logging
import argparse
import tempfile
import colorlog
import pandas as pd
from time import sleep
from queue import Queue
from typing import List
from threading import Lock
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

MAX_RETRIES = 5
BACKOFF_FACTOR = 0.2
FILE_LOCK = Lock()


def init_logging(enable_logging: bool) -> None:
    """Initialize logging.

    Args:
        enable_logging (bool): Flag to enable or disable logging.
    """
    if enable_logging:
        logging.basicConfig(level=logging.INFO)
        logging.info("Logging is enabled.")
        logger = colorlog.getLogger()
        logger.setLevel(logging.INFO)
        handler = colorlog.StreamHandler()
        handler.setFormatter(colorlog.ColoredFormatter(
            '%(log_color)s%(levelname)-8s%(reset)s %(message)s',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        ))
        logger.addHandler(handler)


def dummy_query(conn: sqlite3.Connection) -> bool:
    """Run a dummy query to check for a database lock."""
    cursor = conn.cursor()
    cursor.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='urls'")


def connect_db(path_to_history: str, retries=MAX_RETRIES) -> tuple:
    """Connect to an SQLite database.

    Args:
        path_to_history (str): Path to SQLite database.

    Returns:
        tuple: SQLite connection object if successful and the path to the file. (None, None) otherwise.
    """
    while retries > 0:
        try:
            with sqlite3.connect(path_to_history, isolation_level='IMMEDIATE', check_same_thread=False) as conn:
                dummy_query(conn)  # Check for lock with a dummy query
                logging.info(f"Connected to SQLite database at {path_to_history}")
                return conn, path_to_history  # return the path_to_history to identify if it's a temp db
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                temp_db_path = tempfile.mktemp(suffix=".sqlite")
                shutil.copy2(path_to_history, temp_db_path)
                sleep(BACKOFF_FACTOR * (MAX_RETRIES - retries + 1))
                retries -= 1
                logging.info(
                    f"Database `{path_to_history}` was locked. Created a temporary copy at {temp_db_path}. Try #: {MAX_RETRIES-retries}")
                path_to_history = temp_db_path
            else:
                logging.error(str(e))
                return None, None


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Check if a table exists in the SQLite database.

    Args:
        conn (sqlite3.Connection): SQLite connection object.
        table_name (str): Name of the table to check.

    Returns:
        bool: True if table exists, False otherwise.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    result = cursor.fetchone()
    return result is not None


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
    successful_extractions = 0

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
        'downloads': ("SELECT downloads.target_path, downloads.start_time, downloads.end_time, downloads.total_bytes, downloads.received_bytes, downloads_url_chains.url, downloads.tab_referrer_url, downloads.referrer FROM downloads INNER JOIN downloads_url_chains ON downloads.id=downloads_url_chains.id",
                      ['Target_Path', 'Start_Time', 'End_Time', 'Total_Bytes', 'Received_Bytes', 'URL', 'Tab_Referrer_URL', 'Referrer'], ['Start_Time', 'End_Time'])
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

    error = False
    for extract_type in extract_types:
        query, columns, time_cols = query_dict[extract_type]
        try:
            df = fetch_and_convert_data(query, columns, time_cols)
            for fmt in formats:
                output_file = os.path.normpath(os.path.join(output_dir, f"{output_base}_{extract_type}.{fmt}"))
                if fmt == 'csv':
                    df.to_csv(output_file, index=False)
                elif fmt == 'xlsx':
                    df.to_excel(output_file, index=False, engine='openpyxl')
                elif fmt == 'txt':
                    _pretty_txt(df, output_file)
                logging.info(f"Data saved to {output_file}")
        except sqlite3.OperationalError as e:
            error = True
            if "no such table" in str(e):
                logging.warning(f"The table '{query.split(' ')[3]}' does not exist. Skipping extraction.")
                continue
    if not error:
        successful_extractions = 1
    return successful_extractions


def is_sqlite3(filename: str) -> bool:
    """Check if a file is an SQLite3 database.

    Args:
        filename (str): File path to check.

    Returns:
        bool: True if the file is an SQLite3 database, False otherwise.
    """
    if not os.access(filename, os.R_OK):  # Check for read permission
        logging.error(f"Access denied for {filename}. Ensure you have read permissions.")
        return False
    try:
        with open(filename, 'rb') as f:
            header = f.read(16)
        return header == b'SQLite format 3\x00'
    except Exception as e:
        logging.error(f"Failed to determine if {filename} is an SQLite3 database: {str(e)}")
        return False


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

    output_dir = os.path.normpath(args.dir)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    def _process_history_file(queue, output_dir, formats, extract_types):
        successful_conversions = 0
        while not queue.empty():
            input_path = queue.get()
            logging.info(f"Processing {input_path}")
            try:
                input_path = os.path.normpath(input_path)
                conn, db_path = connect_db(input_path)
                if conn is not None:
                    output_base = os.path.splitext(os.path.basename(input_path))[0]
                    successful_conversions += fetch_and_write_data(conn,
                                                                   output_dir, output_base, formats, extract_types)
                if conn is not None:
                    conn.close()
                if db_path != input_path:
                    with FILE_LOCK:
                        if os.access(db_path, os.W_OK):
                            os.remove(db_path)
            except Exception as e:
                logging.error(f"An error occurred while processing {input_path}: {str(e)}")
        return successful_conversions

    exit_code = 0  # EXIT_SUCCESS
    successful_conversions = 0  # Initialize a counter for successful conversions

    try:
        queue = Queue()
        if args.type == 'folder':
            for filename in os.listdir(args.input):
                input_path = os.path.join(args.input, filename)
                if is_sqlite3(input_path):
                    queue.put(input_path)

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [
                    executor.submit(_process_history_file, queue, args.dir, args.formats, args.extract)
                    for _ in range(min(10, queue.qsize()))]
                print(successful_conversions)
                successful_conversions = sum(future.result() for future in futures)
        else:
            queue.put(args.input)
            successful_conversions = _process_history_file(queue, args.dir, args.formats, args.extract)

        logging.info(f"Successfully converted {successful_conversions} file(s).")

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        exit_code = 2

    return exit_code


if __name__ == "__main__":
    exit(main())
