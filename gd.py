import argparse
import re
import gdown
import os

def extract_id(url):
    # Use a regular expression to extract the file or folder ID from the URL
    file_match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    folder_match = re.search(r'/folders/([a-zA-Z0-9_-]+)', url)
    
    if file_match:
        return file_match.group(1), 'file'
    elif folder_match:
        return folder_match.group(1), 'folder'
    else:
        raise ValueError("Invalid Google Drive URL")

def create_directory_if_not_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Created directory: {path}")
    else:
        print(f"Directory already exists: {path}")

def download_from_google_drive(url, output_path):
    item_id, item_type = extract_id(url)
    create_directory_if_not_exists(os.path.dirname(output_path))
    
    if item_type == 'file':
        gdown.download(f"https://drive.google.com/uc?id={item_id}", output_path, quiet=False)
    elif item_type == 'folder':
        gdown.download_folder(f"https://drive.google.com/drive/folders/{item_id}", output=output_path, quiet=False)

def main():
    parser = argparse.ArgumentParser(description="Download a file or folder from Google Drive and specify the target directory.")
    parser.add_argument("url", help="Google Drive shared URL")
    parser.add_argument("--output", help="Path to the target directory and file name or folder")

    args = parser.parse_args()

    download_from_google_drive(args.url, args.output)

if __name__ == "__main__":
    main()

