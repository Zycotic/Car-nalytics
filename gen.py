import requests
import time
import json
import os
import logging

base_url = "https://paintbytext.chat"
logger = logging.getLogger(__name__)

def generate_image(prompt: str, image: str):
    try:
        logger.info(f"[GEN] Generating image with prompt: {prompt}, image_url: {image}")
        headers = {
            "Referer": base_url + "/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        session = requests.Session()
        session.headers.update(headers)
        response = session.post(
            base_url + "/api/predictions",
            json={"prompt": prompt, "input_image": image}
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"[GEN] Request error: {str(e)}")
        raise Exception(str(e))

    data = response.json()
    generation_id = data["id"]
    logger.info(f"[GEN] Generation ID: {generation_id}")

    tries = 0
    output = None
    while tries < 30:
        try:
            generation_response = session.get(base_url + "/api/predictions/" + generation_id)
            generation_response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"[GEN] Request error: {str(e)}")
            raise Exception(str(e))
        gen_data = generation_response.json()
        logger.info(f"[GEN] Generation status: {gen_data.get('status')}")
        if gen_data.get("status") != "processing" or "completed_at" in gen_data:
            output = gen_data
            logger.info(f"[GEN] Generation completed: {output}")
            break
        tries += 1
        time.sleep(10)  # Sleep for 10 seconds
    return output

def upload_to_imgbb(image_path, api_key):
    try:
        logger.info(f"[GEN] Uploading image to ImgBB: {image_path}")
        url = "https://api.imgbb.com/1/upload"
        with open(image_path, "rb") as file:
            files = {"image": file}
            data = {"key": api_key}
            response = requests.post(url, data=data, files=files)
        response.raise_for_status()
        data = response.json()
        url = data["data"]["url"]
        logger.info(f"[GEN] ImgBB upload response: {response.text}")
        logger.info(f"[GEN] ImgBB uploaded URL: {url}")
        return url
    except Exception as e:
        logger.error(f"[GEN] ImgBB upload error: {str(e)}")
        raise

def print_beautiful_result(result):
    if not result:
        print("No result.")
        return
    # Try to print the output image URL if present
    output = result.get("output")
    if output:
        if isinstance(output, list):
            print("Generated Image(s):")
            for url in output:
                print(f"  {url}")
        else:
            print(f"Generated Image: {output}")
    else:
        print("No output image found.")
    # Pretty print the whole result as JSON
    # print("\nFull response:")
    # print(json.dumps(result, indent=2))
    
def download_generated_images(result, save_dir="downloads"):
    """
    Downloads generated image(s) from the result and saves them locally.
    """
    if not result or "output" not in result:
        print("No output image to download.")
        return

    output = result["output"]
    if not output:
        print("Output is empty or None. No image to download.")
        return

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    timestamp = int(time.time())
    if isinstance(output, list):
        for idx, url in enumerate(output):
            if not url:
                print(f"Image URL at index {idx} is empty. Skipping.")
                continue
            filename = f"generated_{timestamp}_{idx+1}.jpg"
            download_image(url, os.path.join(save_dir, filename))
    else:
        if not output:
            print("Image URL is empty. Skipping download.")
            return
        filename = f"generated_{timestamp}.jpg"
        download_image(output, os.path.join(save_dir, filename))

def download_image(url, filepath):
    """
    Downloads an image from a URL and saves it to the specified filepath.
    """
    response = requests.get(url)
    response.raise_for_status()
    with open(filepath, "wb") as f:
        f.write(response.content)
    print(f"Saved: {filepath}")

if __name__ == "__main__":
    image_url = upload_to_imgbb("GT3.jpg", "515a3a1290d53e22143875f53eaed406")
    # print(f"Image uploaded to ImgBB: {image_url}")
    result = generate_image(
        "Add pirate sticker to the car door",
        image_url
    )
    # print_beautiful_result(result)
    download_generated_images(result)