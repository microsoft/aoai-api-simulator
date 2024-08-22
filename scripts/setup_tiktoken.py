import os
import urllib.request

# Create the tiktoken_cache folder
folder_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "src",
    "aoai-api-simulator",
    "tiktoken_cache",
)

print(folder_path)
os.makedirs(folder_path, exist_ok=True)

# Download the file from the URL
print("Downloading tiktoken encoding file...")
url = "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"
file_path = os.path.join(folder_path, "9b5ad71b2ce5302211f9c61530b329a4922fc6a4")
urllib.request.urlretrieve(url, file_path)
print("Finished tiktoken cache setup.")
