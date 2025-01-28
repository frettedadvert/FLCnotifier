import requests
import yagmail
import json
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Hugging Face Inference API
HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"
HUGGINGFACE_API_TOKEN = "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"  # Replace with your Hugging Face API token

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow logging

websites = [
    {"url": "https://www.deutsches-ausschreibungsblatt.de/branchen/dienstleistungen/catering#/", "keywords": ["lebensmittel", "catering", "verpflegung"]},
]

# Email configuration
EMAIL_ADDRESS = "aaaelbedaway@gmail.com"
EMAIL_PASSWORD = "uhpbpxywxtkmffnp"

# File to store previously found matches
MATCHES_FILE = "matches.json"
TEXT_PARTS_FILE = "extracted_text_parts.json"

def clear_matches_file():
    """Clear the matches.json file."""
    if os.path.exists(MATCHES_FILE):
        with open(MATCHES_FILE, "w") as file:
            json.dump({}, file, indent=4)
        print(f"{MATCHES_FILE} has been cleared.")
    else:
        print(f"{MATCHES_FILE} does not exist. Creating a new empty file.")
        with open(MATCHES_FILE, "w") as file:
            json.dump({}, file, indent=4)

def load_previous_matches():
    """Load previously found matches from a file."""
    if os.path.exists(MATCHES_FILE):
        with open(MATCHES_FILE, "r") as file:
            return json.load(file)
    return {}

def save_matches(matches):
    """Save matches to a file."""
    with open(MATCHES_FILE, "w") as file:
        json.dump(matches, file, indent=4)

def save_text_parts(text_parts):
    """Save extracted text parts to a file."""
    with open(TEXT_PARTS_FILE, "w") as file:
        json.dump(text_parts, file, indent=4)

def query_huggingface_api(extracted_data, keywords, max_length=512):
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"}
    relevant_matches = []

    for i, data in enumerate(extracted_data):
        text = data["title"]
        print(f"Checking text {i+1}/{len(extracted_data)}: {text[:50]}...")

        # Truncate or pad the text
        truncated_text = text[:max_length]

        payload = {
            "inputs": truncated_text,
            "parameters": {"candidate_labels": keywords}
        }

        try:
            response = requests.post(HUGGINGFACE_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

            scores = result.get("scores", [])
            print(scores)
            if any(score > 0.1 for score in scores):
                print(f"Relevant Match Found: {truncated_text}")
                relevant_matches.append({"part": truncated_text, "link": data["link"], "result": result})
        except Exception as e:
            print(f"Error querying Hugging Face API for text {i+1}: {e}")

    return relevant_matches


def extract_titles_with_selenium(url):
    """
    Extract titles and links directly from a dynamically rendered webpage using Selenium.
    Returns an array of dictionaries containing the title and corresponding link.
    """
    # Array to store extracted titles and links
    extracted_data = []

    # Set up Selenium options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    # Add headers to avoid detection
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )

    # Initialize the driver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Load the webpage
        driver.get(url)

        # Handle cookies popup if necessary
        try:
            WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'alle akzeptieren')]"))
            ).click()
            print("Cookies popup dismissed successfully.")
        except Exception:
            print("No cookies popup found.")

        # Wait for the title elements to load
        wait = WebDriverWait(driver, 30)
        title_elements = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "text-blue")))

        print(f"Found {len(title_elements)} elements with class 'text-blue'.")

        # Extract titles and links
        for i, element in enumerate(title_elements, start=1):
            try:
                # Extract text and link
                title = element.text.strip()
                link = element.get_attribute("href")

                # Fallback if text is empty
                if not title:
                    title = element.get_attribute("innerText") or "(No visible text)"
                    title = title.strip()

                
                extracted_data.append({"title": title, "link": link})
                print(f"Extracted {i}: Title: {title}, Link: {link}")

            except Exception as e:
                print(f"Error extracting data from element {i}: {e}")

    except Exception as e:
        print(f"Error extracting titles with Selenium: {e}")

    finally:
        driver.quit()

    return extracted_data


def send_email(new_matches):
    """Send an email notification with titles and links."""
    subject = "Neue Ausschreibungen verfügbar!!"
    body = "Die folgenden neuen Übereinstimmungen wurden gefunden:\n\n"

    for match in new_matches:
        title = match.get("part", "No Title")
        link = match.get("link", "No Link")
        body += f"Title: {title}\nLink: {link}\n\n"

    try:
        yag = yagmail.SMTP(EMAIL_ADDRESS, EMAIL_PASSWORD)
        yag.send("henrik.hemmer@flc-group.de", subject, body)
        print("Email sent!")
    except Exception as e:
        print(f"Failed to send email: {e}")


def main():
    """Main function to check websites and send emails."""
    previous_matches = load_previous_matches()
    print("Previous Matches:", previous_matches)
    new_matches = []

    for site in websites:
        url = site["url"]
        keywords = site["keywords"]

        # Extract all titles and links
        extracted_data = extract_titles_with_selenium(url)
        save_text_parts(extracted_data)

        # Check each title for relevance
        matches = query_huggingface_api(extracted_data, keywords)

        # Determine new matches
        if url not in previous_matches:
            previous_matches[url] = []

        for match in matches:
            if match not in previous_matches[url]:
                new_matches.append(match)
                previous_matches[url].append(match)

    # Send an email if there are new matches
    if new_matches:
        send_email(new_matches)

    # Save the updated matches to the file
    save_matches(previous_matches)

if __name__ == "__main__":
    main()
