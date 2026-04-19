import pickle
import os

# Delete old files if they exist
for file in ['product_data.pkl', 'similarity_matrix.pkl']:
    if os.path.exists(file):
        os.remove(file)
        print(f"Deleted {file}")

# Create fresh files
try:
    with open('product_data.pkl', 'wb') as f:
        pickle.dump({"test": "data"}, f)
    with open('similarity_matrix.pkl', 'wb') as f:
        pickle.dump({"test": "matrix"}, f)
    print("✅ Successfully created fresh .pkl files!")
except Exception as e:
    print(f"❌ Error: {e}")