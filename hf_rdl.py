import argparse
import base64
import json
import requests
import subprocess
import os

parser = argparse.ArgumentParser()
parser.add_argument('-l', '--root', type=str, help='Root of the file or folder to fetch from')
parser.add_argument('-d', '--output', type=str, default='./', help='The folder where the files should be saved.')
args = parser.parse_args()

def to_dl(root):
    parts = root.split('/')
    parts[2] = 'resolve'
    parts = parts[:4]
    dl = '/'.join(parts)
    return dl

def get_items_from_url(root):
    base = "https://huggingface.co/api/models"
    dl_base = "https://huggingface.co"
    url = f"{base}/{root}"
    dl = to_dl(root)
    cursor = None
    items = []
    while True:
        if cursor is None:
            content = requests.get(url).content
        else:
            content = requests.get(f"{url}{cursor.decode()}").content
        dict = json.loads(content)
        if len(dict) == 0 or 'error' in dict:
            break
        items.extend(dict)
        if 'cursor' in dict:
            cursor = base64.b64encode(dict['cursor'].encode())
        else:
            break
    return items, dl_base, dl

def download_file_with_wget(file_url, download_directory):
    subprocess.call(['wget', '-P', download_directory, file_url])

def process_directory(root, output_dir):
    items, dl_base, dl = get_items_from_url(root)
    for item in items:
        if item['type'] == 'file':
            file_url = f"{dl_base}/{dl}/{item['path']}"
            download_file_with_wget(file_url, output_dir)
        elif item['type'] == 'directory':
            new_root = f"{root}/{item['path']}"
            new_output_dir = os.path.join(output_dir, item['path'])
            os.makedirs(new_output_dir, exist_ok=True)
            process_directory(new_root, new_output_dir)

if __name__ == '__main__':
    root = args.root
    output_dir = args.output
    process_directory(root, output_dir)
