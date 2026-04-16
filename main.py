import pandas as pd
import requests
import os
from PIL import Image
from io import BytesIO

# 1. Load Dataset
df = pd.read_csv('./electronics_product.csv') # Sahi path dein

# 2. Create Image Folder
if not os.path.exists('product_images'):
    os.makedirs('product_images')

# 3. Price Cleaning
df['discount_price'] = df['discount_price'].str.replace('₹', '').str.replace(',', '').astype(float)

# 4. Download Function (Sirf pehli 500 images download karein testing ke liye)
def download_images(data, limit=500):
    for i, row in data.head(limit).iterrows():
        try:
            response = requests.get(row['image'], timeout=5)
            img = Image.open(BytesIO(response.content)).convert('RGB').resize((224, 224))
            img.save(f"product_images/{i}.jpg")
            if i % 50 == 0: print(f"Downloaded {i} images...")
        except:
            continue

download_images(df)