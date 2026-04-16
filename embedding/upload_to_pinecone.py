import pandas as pd
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec

# SETUP PINECONE
# Get API key from the Pinecone dashboard
pc = Pinecone(api_key="pcsk_aVQ6i_N7mMoaqtDxXaM2GiRZEMLRUdkqChKWnK2CKexmrBhLR7q5nrFJ4YqrZViR5ay1c")

index_name = "fashion-bot"

# Check if index exists - this must happen BEFORE the loop
if index_name not in [idx.name for idx in pc.list_indexes()]:
    pc.create_index(
        name=multimodal-index,
        dimension=1536, 
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

index = pc.Index(index_name)

#LOAD DATA
# We use on_bad_lines='skip' because some rows in styles.csv can be messy
df = pd.read_csv("styles.csv", on_bad_lines='skip').dropna(subset=['productDisplayName']) 
df = df.head(100) # Processing 100 items first

#LOAD THE EMBEDDING MODEL
model = SentenceTransformer('all-MiniLM-L6-v2')

#UPLOAD TO PINECONE
print("Uploading items...")
for i, row in df.iterrows():
    # We combine name, color, and gender for better search results
    text_to_embed = f"{row['productDisplayName']} {row['baseColour']} for {row['gender']}"
    vector = model.encode(text_to_embed).tolist()
    
    # Uploading WITHOUT price metadata
    index.upsert(vectors=[{
        "id": str(row['id']),
        "values": vector,
        "metadata": {
            "name": row['productDisplayName'],
            "category": row['articleType']
        }
    }])

print("Done! Your data is now in the cloud.")