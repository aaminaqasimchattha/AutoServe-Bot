import os
from PIL import Image
from pinecone import Pinecone
from dotenv import load_dotenv

# SETUP
load_dotenv()
pc = Pinecone(api_key=os.getenv("PINECONE_KEY"))
index = pc.Index("fashion-bot")

# IMAGE FOLDER PATH
IMAGE_FOLDER = os.path.join(os.path.dirname(__file__), "..", "public", "myntradataset", "images") 

def match_and_display_image(image_id):
    """
    Takes an image ID, checks if it exists in Pinecone vector DB,
    and displays the corresponding image if found
    
    Args:
        image_id: Product ID to search for in Pinecone
    
    Returns:
        bool: True if image was found and displayed, False otherwise
    """
    if not image_id:
        print("No image ID provided.")
        return False
    
    try:
        # Fetch the product from Pinecone vector DB using product ID
        result = index.fetch(ids=[str(image_id)])
        
        if result['vectors']:
            vector_data = result['vectors'][0]
            product_id = vector_data['id']
            metadata = vector_data['metadata']
            name = metadata.get('name', 'Unknown Product')
            
            print(f"\nI found this for you: {name}")
            print(f"Product ID: {product_id}")

            # Build image path
            image_path = os.path.join(IMAGE_FOLDER, f"{product_id}.jpg")

            # Check if image exists and display it
            if os.path.exists(image_path):
                print("Opening image...")
                img = Image.open(image_path)
                img.show()
                return True
            else:
                print(f"Product found in database, but image file not found: {image_path}")
                return False
        else:
            print(f"Product ID {image_id} not found in Pinecone vector DB")
            return False
            
    except KeyError as e:
        print(f"Error accessing data: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False
