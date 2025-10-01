#!/usr/bin/env python3
"""
This script recursively downloads files from a Hugging Face Models repository,
preserving the directory structure.

Example Usage:

# Download everything from the 'main' branch of stabilityai/stable-diffusion-xl-base-1.0
python hf_downloader_recursive.py \
  -l https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/tree/main \
  -d ./sdxl_base_model

# Download only the 'text_encoder' subfolder
python hf_downloader_recursive.py \
  -l https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/tree/main/text_encoder \
  -d ./sdxl_text_encoder

# Download a single specific file
python hf_downloader_recursive.py \
  -l https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/model_index.json \
  -d ./sdxl_metadata

# Download a single file using the --file flag (alternative)
python hf_downloader_recursive.py \
  -l https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/tree/main/model_index.json \
  -d ./sdxl_metadata \
  --file
"""

import argparse
import base64
import json
import requests
import subprocess
import os
import re
import time
from urllib.parse import urlparse

# --- Argument Parsing ---
parser = argparse.ArgumentParser(
    description="Recursively download files from a Hugging Face repository.",
    formatter_class=argparse.RawTextHelpFormatter # Keep newline formatting in help
)
parser.add_argument(
    '-l', '--root',
    type=str,
    required=True,
    help='URL pointing to the Hugging Face repository path (directory or file).\n'
         'Examples:\n'
         '  https://huggingface.co/google/flan-t5-base/tree/main\n'
         '  https://huggingface.co/google/flan-t5-base/tree/main/config\n'
         '  https://huggingface.co/google/flan-t5-base/resolve/main/config.json'
)
parser.add_argument(
    '-d', '--output',
    type=str,
    default='./',
    help='The local base directory where files should be saved.\n'
         'The script will recreate the repository\'s subfolder structure within this directory.\n'
         '(default: current directory)'
)
parser.add_argument(
    '--file',
    action="store_true",
    default=False,
    help='Force treating the --root URL as a single file, even if it uses /tree/.\n'
         'Useful if the path happens to look like a directory but is a file.'
)
parser.add_argument(
    '--retries',
    type=int,
    default=3,
    help='Number of retries for failed downloads or API requests (default: 3)'
)
parser.add_argument(
    '--backoff',
    type=float,
    default=1.0,
    help='Exponential backoff factor for retries (default: 1.0 second)'
)


# --- Helper Functions ---

def parse_hf_url(url):
    """
    Parses a Hugging Face URL into repo_id, branch/ref, path, and type.

    Args:
        url (str): The Hugging Face URL.

    Returns:
        tuple: (repo_id, ref, path, is_file_url)
               is_file_url is True if the URL uses '/resolve/' or is forced by --file flag.
               Returns None if parsing fails.
    """
    try:
        parsed = urlparse(url)
        if parsed.netloc != 'huggingface.co':
            print(f"Error: URL '{url}' is not a valid huggingface.co URL.")
            return None

        path_parts = parsed.path.strip('/').split('/')

        # Standard formats:
        # /<user>/<repo>/tree/<ref>/<path...*>
        # /<user>/<repo>/resolve/<ref>/<path...*>
        # /<user>/<repo> (implies tree/main)

        if len(path_parts) < 2:
            print(f"Error: URL path '{parsed.path}' is too short. Expected repo ID.")
            return None

        repo_id = f"{path_parts[0]}/{path_parts[1]}"
        path_type = 'tree' # Default assumption
        ref = 'main'      # Default assumption
        repo_path = ''

        if len(path_parts) > 2:
            path_type = path_parts[2]
            if path_type not in ['tree', 'resolve']:
                # Assume it's part of the repo path with default ref 'main' and type 'tree'
                # e.g., /user/repo/some/path -> tree/main/some/path
                print(f"Warning: URL path segment '{path_type}' is not 'tree' or 'resolve'. Assuming it's part of the path with default branch 'main'.")
                path_type = 'tree'
                ref = 'main'
                repo_path = "/".join(path_parts[2:])
            elif len(path_parts) > 3:
                ref = path_parts[3]
                repo_path = "/".join(path_parts[4:])
            # else: /user/repo/tree|resolve -> implies ref 'main', path ''

        is_file_url = (path_type == 'resolve')

        print(f"Parsed URL: Repo='{repo_id}', Ref='{ref}', Path='{repo_path}', Type='{path_type}'")
        return repo_id, ref, repo_path, is_file_url

    except Exception as e:
        print(f"Error parsing URL '{url}': {e}")
        return None


def get_files_recursive(repo_id, path, ref='main', retries=3, backoff_factor=1.0):
    """
    Recursively fetches file download links and relative paths from a Hugging Face repo path.
    Handles pagination using the cursor from response headers.
    Includes retry logic.

    Args:
        repo_id (str): The repository ID (e.g., 'google/flan-t5-base').
        path (str): The starting path within the repository (can be empty for root).
        ref (str): The branch or commit hash (e.g., 'main').
        retries (int): Number of retries for API requests.
        backoff_factor (float): Base delay for exponential backoff.

    Returns:
        list: A list of tuples: (download_url, relative_save_path)
              Returns an empty list if the path is invalid or no files are found.
    """
    files_to_download = [] # List of tuples: (download_url, relative_save_path)
    cursor = None

    # Construct the base API URL for the *directory* listing
    api_list_url_base = f"https://huggingface.co/api/models/{repo_id}/tree/{ref}/{path}".rstrip('/')

    print(f"\n--- Exploring path: '{path if path else '<root>'}' ---")

    while True:
        url_to_fetch = api_list_url_base
        headers = {'User-Agent': 'hf-downloader-script/1.0'}
        params = {}
        if cursor:
            params['cursor'] = cursor # API expects cursor as query param
            print(f"Fetching next page for '{path if path else '<root>'}': {url_to_fetch}?cursor={cursor[:10]}...")
        else:
            print(f"Fetching initial page for '{path if path else '<root>'}': {url_to_fetch}")

        # --- Attempt API Request with Retries ---
        response = None
        content = None
        current_retry = 0
        while current_retry <= retries:
            try:
                response = requests.get(url_to_fetch, params=params, headers=headers, timeout=60)
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                content = response.json() # Use .json() directly
                break # Success, exit retry loop
            except requests.exceptions.Timeout:
                error_msg = "Timeout"
            except requests.exceptions.RequestException as e:
                error_msg = f"RequestException: {e}"
            except json.JSONDecodeError:
                error_msg = "JSONDecodeError"
                print(f"Response text (first 500 chars): {response.text[:500] if response else 'No response'}...")

            # Handle retry
            current_retry += 1
            if current_retry <= retries:
                wait_time = backoff_factor * (2 ** (current_retry - 1))
                print(f"Error ({error_msg}) fetching {url_to_fetch}. Retrying in {wait_time:.2f}s ({current_retry}/{retries})...")
                time.sleep(wait_time)
            else:
                print(f"Max retries ({retries}) reached for {url_to_fetch}. Error: {error_msg}. Skipping this path/page.")
                # Decide whether to return empty or raise exception. Let's return empty for this path.
                return [] # Return empty list for this failed path exploration

        # --- Process the fetched content ---
        if not isinstance(content, list):
            # Handle API errors returned in JSON format
            if isinstance(content, dict) and 'error' in content:
                error_msg = content.get('error', '')
                print(f"API Error for '{path if path else '<root>'}': {error_msg}")
                # Check if the error indicates the path is a file, not a directory
                # This happens if the initial path given was actually a file path
                if "is not a directory" in error_msg or "Cannot get tree" in error_msg:
                    print(f"Path '{path}' seems to be a file, not a directory.")
                    # If this is the *first* call for this path (no cursor), treat it as a single file.
                    if cursor is None and not files_to_download: # Check if we haven't added anything yet for this path
                        print("Attempting to fetch as a single file.")
                        file_dl_url = f"https://huggingface.co/{repo_id}/resolve/{ref}/{path}"
                        # Check if this file actually exists before adding
                        try:
                            head_response = requests.head(file_dl_url, timeout=10, allow_redirects=True, headers=headers)
                            if head_response.status_code == 200:
                                print(f"  [File] Confirmed single file exists: {path}")
                                files_to_download.append((file_dl_url, path)) # Path is the relative save path
                            else:
                                print(f"  Warning: Single file check failed (Status {head_response.status_code}) for: {path}")
                        except requests.exceptions.RequestException as e:
                            print(f"  Warning: Error checking single file existence for {path}: {e}")
                # Regardless of the specific error, we can't process this response further.
                break # Stop processing this path level

            else:
                print(f"Unexpected API response format (not a list or known error dict) for '{path if path else '<root>'}': {content}")
                break # Stop processing this path level

        if not content: # Empty list means no items (or no more items on this page)
            print(f"No items found on this page for path '{path if path else '<root>'}'.")
            # Continue to cursor check below, as API might send cursor even for empty page
            pass

        # --- Iterate through items in the current page ---
        found_items_on_page = False
        for item in content:
            found_items_on_page = True
            item_path = item.get('path')
            item_type = item.get('type')
            item_size = item.get('size', 'N/A') # Useful info

            if not item_path or not item_type:
                print(f"Warning: Skipping item with missing path or type: {item}")
                continue

            # The 'path' returned by the API is the full path from the repo root.
            full_relative_path = item_path

            if item_type == 'file':
                # Construct download URL using resolve endpoint
                file_dl_url = f"https://huggingface.co/{repo_id}/resolve/{ref}/{full_relative_path}"
                print(f"  [File] Queued: {full_relative_path} (Size: {item_size})")
                files_to_download.append((file_dl_url, full_relative_path))
            elif item_type == 'directory':
                print(f"  [Dir] Found: {full_relative_path}. Descending...")
                # Recursively get files from the subdirectory
                try:
                    # Pass the full relative path to the recursive call
                    sub_files = get_files_recursive(repo_id, full_relative_path, ref, retries, backoff_factor)
                    if sub_files:
                        files_to_download.extend(sub_files)
                    # No explicit "finished exploring" here, happens at the end of the function call for that path
                except Exception as e:
                    # Catch potential errors during recursion (like network issues deeper down)
                    print(f"Warning: Error processing subdirectory {full_relative_path}: {e}. Continuing...")
            # else: ignore other types like 'symlink' if any

        # --- Check for pagination cursor ---
        # Use response headers (common pattern: X-Next-Cursor)
        next_cursor_header = response.headers.get('X-Next-Cursor')
        if next_cursor_header:
            print(f"Found cursor in header for next page of '{path if path else '<root>'}'.")
            cursor = next_cursor_header # Use the cursor string directly
        else:
            # No cursor found in header, assume end of list for this directory level
            print(f"No cursor found in headers for path '{path if path else '<root>'}'. Assuming end of directory listing.")
            break # Exit the 'while True' loop for this directory level

        # Safety break: If API returned an empty list AND no cursor, we should stop.
        if not found_items_on_page and not next_cursor_header:
             print(f"Empty page and no cursor for path '{path if path else '<root>'}'. Stopping exploration for this path.")
             break

    print(f"--- Finished exploring path: '{path if path else '<root>'}' ---")
    return files_to_download


def download_file_with_wget(file_url, save_path, retries=3, backoff_factor=1.0):
    """
    Uses wget to download a file from a given URL to a specified *full path*.
    Includes retry logic.

    Args:
        file_url (str): The URL of the file to download.
        save_path (str): The full local path (including filename) where the file should be saved.
        retries (int): Number of download retries.
        backoff_factor (float): Base delay for exponential backoff.

    Returns:
        bool: True if download was successful or file already exists and is complete, False otherwise.
    """
    download_directory = os.path.dirname(save_path)
    filename = os.path.basename(save_path) # wget needs the dir and saves with original name

    # Create the target directory structure if it doesn't exist
    if download_directory: # Avoid trying to create '.'
        os.makedirs(download_directory, exist_ok=True)

    # Check if wget exists
    try:
        subprocess.run(['wget', '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: 'wget' command not found or not executable. Please install wget.")
        return False

    print(f"\nDownloading: {file_url}")
    print(f"       to: {save_path}")

    # wget command arguments:
    # -P <dir>: Save files to directory <dir>.
    # -O <file>: Save to specific file path (overwrites -P filename behavior). Use this for precise control.
    # -c : Continue getting a partially-downloaded file.
    # -nv: Non-verbose, less output.
    # --show-progress: Show progress bar even with -nv.
    # --tries=<n>: Set number of retries (0 = infinite). Let our script handle retries.
    # --waitretry=<sec>: Wait seconds between retries (wget default).
    # --retry-connrefused: Retry even if connection is refused.
    # -T <sec>: Set network timeout.

    current_retry = 0
    while current_retry <= retries:
        try:
            # Use -O to specify the exact output path, -c to resume
            process = subprocess.run(
                ['wget', '-c', '-O', save_path, '-nv', '--show-progress', '--timeout=60', '--tries=1', file_url],
                check=True,
                capture_output=True, # Capture stderr for potential errors
                text=True
            )
            print(f"Successfully downloaded: {filename}")
            return True # Success
        except subprocess.CalledProcessError as e:
            error_msg = f"wget exited with error (code {e.returncode})"
            # Check stderr for common wget errors
            stderr_output = e.stderr.lower()
            if "file exists" in stderr_output and "already fully retrieved" in stderr_output:
                 print(f"File already exists and is complete: {filename}")
                 return True # Treat as success
            if "connection refused" in stderr_output:
                 error_msg += " (Connection Refused)"
            elif "timed out" in stderr_output:
                 error_msg += " (Timeout)"

            # Handle retry
            current_retry += 1
            if current_retry <= retries:
                wait_time = backoff_factor * (2 ** (current_retry - 1))
                print(f"Error downloading {filename}: {error_msg}. Retrying in {wait_time:.2f}s ({current_retry}/{retries})...")
                # print(f"wget stderr: {e.stderr.strip()}") # Optional: more detailed error
                time.sleep(wait_time)
            else:
                print(f"Max retries ({retries}) reached for {filename}. Error: {error_msg}.")
                print(f"wget stderr: {e.stderr.strip()}")
                # Optionally remove partially downloaded file
                # try:
                #     if os.path.exists(save_path): os.remove(save_path)
                # except OSError as rm_err:
                #     print(f"Warning: Could not remove partial file {save_path}: {rm_err}")
                return False # Failed after retries

    return False # Should not be reached if retries >= 0


# --- Main Execution ---
if __name__ == '__main__':
    args = parser.parse_args()

    print("--- Hugging Face Downloader ---")
    print(f"Input URL: {args.root}")
    print(f"Output Dir: {args.output}")
    print(f"Force File: {args.file}")
    print(f"Retries: {args.retries}")
    print(f"Backoff: {args.backoff}")
    print("-" * 30)


    parsed_info = parse_hf_url(args.root)
    if not parsed_info:
        exit(1) # Error message already printed by parser

    repo_id, ref, initial_path, is_file_url = parsed_info
    force_single_file = args.file

    files_to_download = []

    try:
        # Case 1: URL points directly to a file (/resolve/)
        if is_file_url and not force_single_file:
            print("URL detected as a direct file link (/resolve/).")
            # The URL itself is the download link
            # The path is the relative path for saving
            # Need to check file existence first? get_files_recursive handles this somewhat.
            # Let's try fetching it as if it were a directory containing only itself.
            # This reuses the checking logic within get_files_recursive.
            files_to_download = get_files_recursive(repo_id, initial_path, ref, args.retries, args.backoff)
            if not files_to_download:
                 print(f"Warning: Direct file URL {args.root} could not be verified or fetched.")


        # Case 2: User forces file interpretation (--file)
        elif force_single_file:
            print("Processing as single file due to --file flag.")
            # Construct the download URL assuming initial_path is the file path
            file_dl_url = f"https://huggingface.co/{repo_id}/resolve/{ref}/{initial_path}"
            # We should ideally check if it exists, but let's just add it and let wget handle errors
            print(f"  [File] Queued (forced): {initial_path}")
            files_to_download.append((file_dl_url, initial_path))

        # Case 3: URL points to a directory (/tree/ or implied)
        else:
            print("URL detected as directory link (/tree/ or root). Fetching recursively...")
            files_to_download = get_files_recursive(repo_id, initial_path, ref, args.retries, args.backoff)

    except Exception as e:
        print(f"\nAn unexpected error occurred during file listing: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

    # --- Download the collected files ---
    if not files_to_download:
        print("\nNo files found or collected to download.")
    else:
        print(f"\n--- Starting Download of {len(files_to_download)} files ---")
        successful_downloads = 0
        failed_downloads = 0

        # Create the base output directory if it doesn't exist
        os.makedirs(args.output, exist_ok=True)

        for dl_url, relative_path in files_to_download:
            # Construct the full local path including subdirectories
            # os.path.join handles paths correctly
            # Ensure relative_path doesn't start with / if args.output is relative
            safe_relative_path = relative_path.lstrip('/')
            full_save_path = os.path.join(args.output, safe_relative_path)

            if download_file_with_wget(dl_url, full_save_path, args.retries, args.backoff):
                successful_downloads += 1
            else:
                failed_downloads += 1
                print(f"Failed to download: {relative_path}")

        print("\n--- Download Summary ---")
        print(f"Successfully downloaded: {successful_downloads}")
        print(f"Failed downloads: {failed_downloads}")
        print("-" * 30)

        if failed_downloads > 0:
            print("Some files failed to download. Check the output above for details.")
            exit(1) # Exit with error code if any download failed

    print("Download process finished.")
    exit(0)


# python hf_recur.py -l https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct/tree/main -d /work/nvme/befh/qwu4/code/GoT/pretrained
# python hf_recur.py -l https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/tree/main -d /work/nvme/befh/qwu4/code/GoT/pretrained