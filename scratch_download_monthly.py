import requests
from bs4 import BeautifulSoup
import os
import sys
import time

def download_histdata_month(pair='xauusd', year='2025', month='1'):
    url = f"https://www.histdata.com/download-free-forex-historical-data/?/metatrader/1-minute-bar-quotes/{pair}/{year}/{month}"
    print(f"Fetching token from {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    session = requests.Session()
    response = session.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch page. Status: {response.status_code}")
        return False
        
    soup = BeautifulSoup(response.text, 'html.parser')
    form = soup.find('form', {'id': 'file_down'})
    
    if not form:
        print("Failed to find download form on page")
        return False
        
    data = {}
    for input_tag in form.find_all('input'):
        name = input_tag.get('name')
        value = input_tag.get('value')
        if name:
            data[name] = value
            
    print(f"Found form data: tk={data.get('tk')[:10]}...")
    
    download_url = "https://www.histdata.com/get_file.php"
    headers['Referer'] = url
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
    
    dl_response = session.post(download_url, data=data, headers=headers, stream=True)
    
    if dl_response.status_code != 200:
        print(f"Failed to download {year}/{month}. Status: {dl_response.status_code}")
        return False
        
    filename = dl_response.headers.get('content-disposition', '').split('filename=')[-1].strip('"')
    if not filename:
        filename = f"HISTDATA_COM_MT_{pair.upper()}_M1_{year}{int(month):02d}.zip"
        
    out_dir = "/storage/emulated/0/Download"
    out_path = os.path.join(out_dir, filename)
    
    with open(out_path, 'wb') as f:
        for chunk in dl_response.iter_content(chunk_size=8192):
            f.write(chunk)
            
    print(f"Successfully downloaded to: {out_path}")
    return True

if __name__ == "__main__":
    for m in range(1, 13):
        download_histdata_month('xauusd', '2025', str(m))
        time.sleep(2)
