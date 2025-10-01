"""
This script is used to download files from a Hugging Face Datasets repository.

Suppose you are going to download the files under the following URL:
https://huggingface.co/datasets/tiange/Cap3D/tree/main/PointCloud_pt_zips

You can use the following command to download the file:
python hf_ds.py -l tiange/Cap3D/tree/main/PointCloud_pt_zips -d ./PointCloud_pt_zips
"""

import argparse
import base64
import json
from pathlib import Path
import requests
import subprocess
import os

parser = argparse.ArgumentParser()
parser.add_argument('-l','--root', type=str, help='Root of the file to fetch from')
parser.add_argument('-d', '--output', type=str, default='./', help='The folder where the files should be saved.')
args = parser.parse_args()


def to_dl(root):
    parts = root.split('/')

    #parts.insert(2, 'resolve')
    if parts[-1] != 'main':
        parts[2] = 'resolve'
        parts = parts[:-1]
    else:
        parts[2] = 'resolve'


    dl = '/'.join(parts)
    return dl

# def to_dl(root):
#     parts = root.split('/')
    
#     if len(parts) >= 3:  # Ensure there are at least 3 parts
#         parts[2] = 'resolve'
#         parts = parts[:-1]
#     else:
#         return root  # Return the original root if it's too short
    
#     dl = '/'.join(parts)
#     return dl
                
def get_download_links_from_url(root):
    base = "https://huggingface.co/api/datasets"
    dl_base = "https://huggingface.co/datasets"
    url = f"{base}/{root}"
    dl = to_dl(root)

    cursor = None

    links = []

    while True:
        if cursor is None:
            content = requests.get(url).content
            print(url)
        else:
            content = requests.get(f"{url}{cursor.decode()}").content
            print(f"{url}{cursor.decode()}")
        print(content)
        dict = json.loads(content)
        if len(dict) == 0 or 'error' in dict:
            break

        if 'cursor' in dict:
            cursor = base64.b64encode(dict['cursor'].encode())
        else:
            break


    for i in range(len(dict)):
        fname = dict[i]['path']
        print(fname)
        
        links.append(f"{dl_base}/{dl}/{fname}")
      

    return links



    


def download_file_with_wget(file_url, download_directory):
    """
    Uses wget to download a file from a given URL to a specified directory.
    """
    subprocess.call(['wget', '-P', download_directory, file_url])

if __name__ == '__main__':
    root = args.root

    if not os.path.exists(args.output):
        os.makedirs(args.output, exist_ok=True)

    links = get_download_links_from_url(root) #get_download_links_from_url(url)
    print(links)
    #exit()
    for l in links:
        download_file_with_wget(l, args.output)

