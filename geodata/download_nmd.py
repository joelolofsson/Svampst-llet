import urllib.request
import zipfile
import os

url = "https://geodata.naturvardsverket.se/nedladdning/marktacke/NMD2023/Basskikt_v2_x/NMD2023_basskikt_v2_1.zip"
zip_path = "NMD2023_basskikt_v2_1.zip"

if not os.path.exists("NMD2023bas_v2_1.tif"):
    if not os.path.exists(zip_path):
        print(f"Laddar ner {url}...")
        urllib.request.urlretrieve(url, zip_path)
    print("Packar upp zip-filen...")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall()
    print("Nedladdning och uppackning klar!")
else:
    print("Filen finns redan, hoppar över nedladdning.")
