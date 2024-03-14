# Description: Download a file from Google Drive 

# Usage: python gd.py <URL> --output <output_dir>

import argparse
import re
import gdown

def extract_file_id(url):
    # Use a regular expression to extract the file ID from the URL
    match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    else:
        raise ValueError("Invalid Google Drive URL")

def download_from_google_drive(url, output_path):
    file_id = extract_file_id(url)
    gdown.download(f"https://drive.google.com/uc?id={file_id}", output_path, quiet=False)

def main():
    parser = argparse.ArgumentParser(description="Download a file from Google Drive and specify the target directory.")
    parser.add_argument("url", help="Google Drive shared URL")
    parser.add_argument("--output", default='./', help="Path to the target directory and file name")

    args = parser.parse_args()

    download_from_google_drive(args.url, args.output)

if __name__ == "__main__":
    main()
