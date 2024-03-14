"""
Description: Download from website with Google Drive links

Usage: python dl.py <URL> <output_dir>

Author: Qifeng Wu
"""

import requests
from bs4 import BeautifulSoup
from gd import download_from_google_drive
import os
import argparse

# Create a parser object
parser = argparse.ArgumentParser(description='Download files from a webpage')

# Add a positional argument
parser.add_argument('url', type=str, help='URL of the webpage', default='https://eyecan-ai.github.io/eyecandies/download')
parser.add_argument('output_dir', type=str, help='Output directory')

# Parse the arguments
args = parser.parse_args()


# Send a request to the webpage
response = requests.get(args.url)

# Check if the request was successful
if response.status_code == 200:
    # Parse the webpage content
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find all hyperlinks in the webpage
    links = soup.find_all('a')
    
    #Extract Google Drive links
    drive_links = [link.get('href') for link in links if link.get('href') and 'drive.google.com' in link.get('href')]

    # Print the extracted links
    for link in drive_links:
        print(link)

    #print(links)
else:
    print("Failed to retrieve the webpage")

if not os.path.exists(args.output_dir):
    os.makedirs(args.output_dir, exist_ok=True)

# Download the file from Google Drive
for link in drive_links:
    download_from_google_drive(link, args.output_dir)





