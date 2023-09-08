# History Exporter

![Build Status](https://img.shields.io/badge/build-passing-green)
![GitHub release](https://img.shields.io/github/release/darkarp/histexport.svg)
![License](https://img.shields.io/github/license/darkarp/histexport.svg)

## Table of Contents

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
  - [Command Line Interface](#command-line-interface)
- [Data Extraction](#data-extraction)
- [Output Formats](#output-formats)
- [Logging](#logging)
- [License](#license)

## Introduction

HistoryExtractor is a Python utility aimed at exporting Chromium-based browser history and downloads data to various formats such as CSV, XLSX, and TXT. Designed with a focus on user flexibility and data granularity, this tool provides customizable extraction options to suit different investigative or analytic needs.

## Prerequisites

- Python 3.7+

## Installation

### Method 1: Using pip

You can install `histexport` directly using pip:
  ```
  pip install histexport
  ```  

### Method 2: From GitHub Repository

1. Clone the GitHub repository.
  ```
  git clone https://github.com/darkarp/histexport.git
  ```
2. Navigate to the project directory.
  ```
  cd histexport
  ```
3. Install the required Python packages.
  ```
  pip install -e .
  ```  

Either of these methods will install the required Python packages and make `histexport` available for use.

## Usage

### Command Line Interface

1. Basic extraction of URLs and Downloads:
 ```
 histexport -i path/to/history -o output_name
 ```

2. Specify output directory and formats:
 ```
 histexport -i path/to/history -o output_name -d path/to/output -f csv xlsx
 ```

3. Enable logging:
 ```
 histexport -i path/to/history -o output_name -l
 ```  

4. Extract from a folder of SQLite files:
 ```
 histexport -i path/to/history_folder -t folder -o output_name -d path/to/output -f csv xlsx -e urls downloads
 ```

#### Arguments

- `-i`, `--input`: Path to the SQLite history file. (required)
- `-t`, `--type`: Type of the input: file or folder. Default is file
- `-o`, `--output`: Base name for output files. (required)
- `-d`, `--dir`: Output directory. (optional, default is `./`)
- `-f`, `--formats`: Output formats (csv, xlsx, txt). (optional, default is `txt`)
- `-e`, `--extract`: Data to extract (urls, downloads). (optional, default is both)
- `-l`, `--log`: Enable logging. (optional, default is disabled)

## Data Extraction

The tool allows extraction of:

- URLs: Fetches `URL`, `Title`, `Visit_Count`, and `Last_Visit_Time`.
- Downloads: Extracts `Target_Path`, `Start_Time`, `End_Time`, `Total_Bytes`, `Received_Bytes`, and `URL`.

## Output Formats

You can export the data into:

- CSV
- XLSX (Excel)
- TXT (Pretty printed text file)

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE) file for details.

