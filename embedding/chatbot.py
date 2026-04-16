import os
from PIL import Image  # This handles the images
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone
from dotenv import load_dotenv
#SETUP
load_dotenv()
pc = Pinecone(api_key=os.getenv("PINECONE_KEY"))
index = pc.Index("fashion-bot")
model = SentenceTransformer('all-MiniLM-L6-v2')

#IMAGE FOLDER PATH
# This tells the bot where your images are saved
IMAGE_FOLDER = "images" 

def ask_bot(question):
    # Turn the user's question into numbers
    query_vector = model.encode(question).tolist()
    
    # Search Pinecone for the top 1 item (the best match)
    results = index.query(vector=query_vector, top_k=1, include_metadata=True)
    
    if results['matches']:
        match = results['matches'][0]
        product_id = match['id']
        name = match['metadata']['name']
        
        print(f"\nI found this for you: {name}")
        print(f"Product ID: {product_id}")

        #OPEN THE IMAGE
        # It looks for a file like '15970.jpg' inside the 'images' folder
        image_path = os.path.join(IMAGE_FOLDER, f"{product_id}.jpg")

        if os.path.exists(image_path):
            print("Opening image...")
            img = Image.open(image_path)
            img.show() 
        else:
            print(f"Match found, but I can't find the image file: {image_path}")
    else:
        print("Sorry, I couldn't find anything matching that description.")

#START THE CHAT
while True:
    user_input = input("\nWhat are you looking for? (or type 'exit' to stop): ")
    if user_input.lower() == 'exit':
        break
    ask_bot(user_input)
