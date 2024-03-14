"""
This script is used to download files from a Hugging Face Models repository.

Suppose you are going to download files under the following URL:
https://huggingface.co/Alpha-VLLM/LLaMA2-Accessory/tree/main/finetune/mm/alpacaLlava_llamaQformerv2_13b

You can use the following command to download the file:
python hf_nn.py -l Alpha-VLLM/LLaMA2-Accessory/tree/main/finetune/mm/alpacaLlava_llamaQformerv2_13b -d ./PointCloud_pt_zips
"""

import argparse
import base64
import json
import requests
import subprocess

parser = argparse.ArgumentParser()
parser = argparse.ArgumentParser()
parser.add_argument('-l', '--root', type=str, help='Root of the file to fetch from')
parser.add_argument('-d', '--output', type=str, default='./', help='The folder where the files should be saved.')
args = parser.parse_args()


def to_dl(root):
    parts = root.split('/')

    #parts.insert(2, 'resolve')
    parts[2] = 'resolve'
    parts = parts[:4]
    dl = '/'.join(parts)
    return dl
                
def get_download_links_from_url(root):
    #https://huggingface.co/api/models/Alpha-VLLM/LLaMA2-Accessory/tree/main/finetune/mm/alpacaLlava_llamaQformerv2_13b
    base = "https://huggingface.co/api/models"
    dl_base = "https://huggingface.co"
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
    links = get_download_links_from_url(root) #get_download_links_from_url(url)
    for l in links:
        download_file_with_wget(l, args.output)


