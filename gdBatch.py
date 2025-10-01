from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

def authenticate_service_account():
    gauth = GoogleAuth()
    gauth.ServiceAuth()
    return GoogleDrive(gauth)

def download_file(file, file_path):
    if os.path.exists(file_path):
        print(f"⏭️ Skipping (already exists): {file['title']}")
        return
    print(f"⬇️ Downloading: {file['title']}")
    file.GetContentFile(file_path)

def download_folder_recursive(drive, folder_id, save_path, executor):
    if not os.path.exists(save_path):
        os.makedirs(save_path)

    file_list = drive.ListFile({'q': f"'{folder_id}' in parents and trashed=false"}).GetList()
    futures = []

    for file in file_list:
        file_path = os.path.join(save_path, file['title'])

        if file['mimeType'] == 'application/vnd.google-apps.folder':
            print(f"📁 Entering folder: {file['title']}")
            download_folder_recursive(drive, file['id'], file_path, executor)
        else:
            futures.append(executor.submit(download_file, file, file_path))

    # Wait for all current folder downloads to finish
    for future in as_completed(futures):
        future.result()

def main():
    folder_id = '1Af7wcE1EkGdeVmd8wbjvy4qCjejE2RCW'
    output_path = '/mnt/data1/lv0/scratch/home/v_qifeng_wu/data/em/2d'

    drive = authenticate_service_account()

    with ThreadPoolExecutor(max_workers=8) as executor:
        download_folder_recursive(drive, folder_id, output_path, executor)

if __name__ == "__main__":
    main()
