import os
import re
import sys
import json
import requests
import openai

###############################################################################
# 1. CONFIGURATION: API KEYS AND ENDPOINTS
###############################################################################

# Retrieve API keys from environment variables (GitHub Actions or local .env)
NEWS_API_URL = "https://newsapi.org/v2/top-headlines"
NEWS_API_KEY = os.getenv("NEWS_API_KEY")  # Securely fetch from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Securely fetch from environment
WP_ACCESS_TOKEN = os.getenv("WP_ACCESS_TOKEN")  # Securely fetch from environment
WP_BLOG_ID = "241913052"

# Validate that all required secrets are set
if not all([NEWS_API_KEY, OPENAI_API_KEY, WP_ACCESS_TOKEN]):
    raise ValueError("Error: One or more required API keys are missing. Check environment variables.")

# Configure OpenAI API
openai.api_key = OPENAI_API_KEY

# WordPress REST API Endpoints
WP_MEDIA_URL = f"https://public-api.wordpress.com/rest/v1/sites/{WP_BLOG_ID}/media/new"
WP_POSTS_URL = f"https://public-api.wordpress.com/rest/v1/sites/{WP_BLOG_ID}/posts/new"

# Common headers for WordPress
WP_HEADERS = {
    "Authorization": f"Bearer {WP_ACCESS_TOKEN}"
}

###############################################################################
# 2. FETCH NEWS ARTICLES (Finance, Business, Tech)
###############################################################################

def fetch_top_headlines():
    """
    Fetch the top 2 headlines from each of three news categories/topics:
      1) Finance (simulated via 'q=finance')
      2) Business (category=business)
      3) Tech (category=technology)

    Returns:
        dict: { "finance": [...], "business": [...], "tech": [...] }
    """
    results = {
        "finance": [],
        "business": [],
        "tech": []
    }

    # -- Finance (via query) --
    finance_params = {
        "country": "us",
        "q": "finance",
        "pageSize": 2,
        "apiKey": NEWS_API_KEY
    }
    try:
        resp = requests.get(NEWS_API_URL, params=finance_params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results["finance"] = data.get("articles", [])
        print(f"[INFO] Fetched {len(results['finance'])} finance articles.")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to get finance headlines: {e}")

    # -- Business --
    business_params = {
        "country": "us",
        "category": "business",
        "pageSize": 2,
        "apiKey": NEWS_API_KEY
    }
    try:
        resp = requests.get(NEWS_API_URL, params=business_params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results["business"] = data.get("articles", [])
        print(f"[INFO] Fetched {len(results['business'])} business articles.")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to get business headlines: {e}")

    # -- Tech --
    tech_params = {
        "country": "us",
        "category": "technology",
        "pageSize": 2,
        "apiKey": NEWS_API_KEY
    }
    try:
        resp = requests.get(NEWS_API_URL, params=tech_params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results["tech"] = data.get("articles", [])
        print(f"[INFO] Fetched {len(results['tech'])} tech articles.")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to get tech headlines: {e}")

    # Optionally, if no articles are found at all, exit or handle accordingly
    total_articles = sum(len(v) for v in results.values())
    if total_articles == 0:
        print("[INFO] No articles found for any category. Exiting.")
        sys.exit(0)

    return results


###############################################################################
# 3. REWRITE ARTICLE CONTENT USING OPENAI
###############################################################################

def rewrite_article(title, description, content):
    """
    Uses OpenAI (GPT-3.5-turbo) to rewrite the article in a professional news style.
    Returns the rewritten text or a fallback message if there's an error.
    """
    prompt_text = (
        "Please read the following article and rewrite it in an informative, "
        "concise, and professional news-style format. **Do NOT restate the title "
        "verbatim as the first line.** Instead, begin with a short introduction. "
        "Use 400-800 words (or ~1500 tokens). Keep the essential details.\n\n"
        f"Title: {title}\n\n"
        f"Description: {description}\n\n"
        f"Content: {content}\n\n"
        "Rewrite the article while keeping the key details."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a professional news writer."},
                {"role": "user", "content": prompt_text}
            ],
            temperature=0.7
        )
        rewritten_text = response.choices[0].message.content.strip()
        return rewritten_text
    except Exception as e:
        print(f"[ERROR] OpenAI API call failed: {e}")
        return "Error: Could not rewrite article using OpenAI API."


###############################################################################
# 4. DOWNLOAD IMAGE LOCALLY
###############################################################################

def download_image(image_url, local_filename):
    """
    Downloads an image from 'image_url' and saves it to 'local_filename'.
    Returns True on success, False on failure.
    """
    if not image_url:
        return False

    # Custom headers to mimic a real browser request
    headers_for_image = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/100.0.4896.60 Safari/537.36"
        ),
        "Referer": "https://www.google.com/"
    }

    try:
        response = requests.get(image_url, headers=headers_for_image, timeout=15)
        if response.status_code == 200:
            with open(local_filename, "wb") as f:
                f.write(response.content)
            print(f"[INFO] Image downloaded successfully: {local_filename}")
            return True
        else:
            print(f"[WARN] Failed to download image. HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Exception while downloading {image_url}: {e}")
        return False


###############################################################################
# 5. UPLOAD LOCAL IMAGE TO WORDPRESS
###############################################################################

def upload_local_image(image_path):
    """
    Uploads a local image file to WordPress media library.
    Returns (attachment_id, media_link) on success, or (None, None) on failure.
    """
    if not os.path.exists(image_path):
        print(f"[WARN] File not found: {image_path}")
        return None, None

    filename = os.path.basename(image_path)
    ext = os.path.splitext(filename)[1].lower()

    # Determine the MIME type
    if ext in [".jpg", ".jpeg"]:
        content_type = "image/jpeg"
    elif ext == ".png":
        content_type = "image/png"
    elif ext == ".gif":
        content_type = "image/gif"
    else:
        content_type = "application/octet-stream"

    # Prepare the file for upload
    with open(image_path, "rb") as f:
        files = {
            "media[]": (filename, f.read(), content_type)
        }

    try:
        resp = requests.post(WP_MEDIA_URL, headers=WP_HEADERS, files=files, timeout=15)
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to upload image to WordPress: {e}")
        return None, None

    if resp.status_code not in (200, 201):
        print(f"[ERROR] WordPress media upload failed: HTTP {resp.status_code} - {resp.text}")
        return None, None

    resp_json = resp.json()
    media = resp_json.get("media", [])
    if not media or len(media) == 0:
        print("[ERROR] Unexpected response structure from WP media upload.")
        return None, None

    # The WordPress API (v1) returns 'id' and 'link' in the first element of the 'media' list
    attachment_id = media[0].get("id")
    media_link = media[0].get("link")

    print(f"[INFO] Uploaded image to WordPress. Attachment ID: {attachment_id}, Link: {media_link}")
    return attachment_id, media_link


###############################################################################
# 6. CREATE (OR PUBLISH) A WORDPRESS POST
###############################################################################

def create_wordpress_post(title, content, attachment_id=None):
    """
    Creates a WordPress post with the given title and content, optionally setting
    the featured image if attachment_id is provided. Uses the 'Daily' category.
    """
    post_data = {
        "title": title,
        "content": content,
        "status": "publish",
        "categories": ["Daily"]  # Example category
    }
    if attachment_id:
        # For WordPress.com REST v1, it's "featured_image" not "featured_media"
        post_data["featured_image"] = attachment_id

    try:
        resp = requests.post(WP_POSTS_URL, headers=WP_HEADERS, json=post_data, timeout=15)
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to create post: {e}")
        return False

    if resp.status_code in (200, 201):
        print(f"[INFO] Post '{title}' created successfully!")
        return True
    else:
        print(f"[ERROR] Failed to create post '{title}': HTTP {resp.status_code} - {resp.text}")
        return False


###############################################################################
# 7. MAIN WORKFLOW
###############################################################################

def main():
    # 1. Fetch the latest articles from NewsAPI (finance, business, tech)
    headlines_by_category = fetch_top_headlines()

    # 2. Iterate through each category, then each article
    for category, articles in headlines_by_category.items():
        for idx, article in enumerate(articles, start=1):
            original_title = article.get("title") or "No Title"
            # Clean up the title to remove any trailing " - ... " or " – ... "
            original_title = re.sub(r'\s[-–—]\s.*$', '', original_title)

            description = article.get("description", "")
            content = article.get("content", "")
            image_url = article.get("urlToImage", "")

            # --- A) If there's no image URL at all, skip immediately ---
            if not image_url:
                print(f"[INFO] No image URL for article '{original_title}'. Skipping.")
                continue

            # --- B) Rewrite Article with OpenAI ---
            rewritten_content = rewrite_article(original_title, description, content)

            # --- C) Attempt to Download Image Locally ---
            # Attempt to guess a file extension
            ext = os.path.splitext(image_url)[1]
            # If the URL doesn't have a valid extension or it's too long, default to .jpg
            if not ext or len(ext) > 5:
                ext = ".jpg"

            local_filename = f"temp_image_{category}_{idx}{ext}"
            downloaded_ok = download_image(image_url, local_filename)
            if not downloaded_ok:
                print(f"[INFO] Failed to download image for '{original_title}'. Skipping.")
                continue

            # --- D) Upload the downloaded file to WordPress ---
            attachment_id, _ = upload_local_image(local_filename)
            # Clean up the temp file
            try:
                os.remove(local_filename)
            except OSError:
                pass

            if not attachment_id:
                print(f"[INFO] No attachment_id returned for '{original_title}'. Skipping.")
                continue

            # --- E) Create WordPress Post with the featured image ---
            post_created = create_wordpress_post(original_title, rewritten_content, attachment_id)
            if post_created:
                print(f"[INFO] Successfully published post for '{original_title}' in category '{category}'.")
            else:
                print(f"[ERROR] Could not publish post for '{original_title}' in category '{category}'.")


if __name__ == "__main__":
    main()