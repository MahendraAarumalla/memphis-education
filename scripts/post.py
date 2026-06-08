"""
LinkedIn daily posting automation — From Memphis to 50 States challenge.

Scheduling: matches today's date against scheduled_date in posts/dayN.json.
Image: uses pre-built dayN/linkedin-post.png (Figma export).
Logs every run to logs/post_log.txt with timestamp.
Sends email notification to NOTIFY_EMAIL after each successful post.
"""
import json
import os
import sys
import time
import urllib.parse
import subprocess
import smtplib
from email.mime.text import MIMEText
from datetime import date
from pathlib import Path

import requests

LI_TOKEN          = os.environ["LINKEDIN_ACCESS_TOKEN"]
LI_PERSON_URN     = os.environ["LINKEDIN_PERSON_URN"]
GMAIL_USER        = os.environ.get("GMAIL_USER", "mahendragudipadu@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL      = "mahendragudipadu@gmail.com"

REPO_ROOT = Path(__file__).parent.parent
LOG_FILE  = REPO_ROOT / "logs" / "post_log.txt"


# ── Logging ───────────────────────────────────────────────────────────────────
def log(msg):
    LOG_FILE.parent.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    line = f"[{timestamp}] {msg}"
    print(line)
    with LOG_FILE.open("a") as f:
        f.write(line + "\n")


# ── 1. Find today's post by scheduled_date ────────────────────────────────────
def load_todays_post():
    today = date.today().isoformat()          # "2026-06-08"
    for fpath in sorted(REPO_ROOT.glob("posts/day*.json")):
        data = json.loads(fpath.read_text())
        if data.get("scheduled_date") == today:
            return fpath, data
    return None, None


# ── 2. Load pre-built Figma image ─────────────────────────────────────────────
def load_image(post_data):
    path = REPO_ROOT / post_data["image_path"]
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    log(f"Image loaded: {post_data['image_path']} ({path.stat().st_size // 1024}KB)")
    return path.read_bytes()


# ── 3. Upload image to LinkedIn ───────────────────────────────────────────────
def upload_image(image_bytes):
    headers = {
        "Authorization":             f"Bearer {LI_TOKEN}",
        "Content-Type":              "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    reg = requests.post(
        "https://api.linkedin.com/v2/assets?action=registerUpload",
        headers=headers,
        json={
            "registerUploadRequest": {
                "recipes":  ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner":    LI_PERSON_URN,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier":       "urn:li:userGeneratedContent",
                }],
            }
        },
    )
    reg.raise_for_status()
    reg_data   = reg.json()["value"]
    upload_url = reg_data["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    asset_urn  = reg_data["asset"]

    put = requests.put(
        upload_url,
        headers={"Authorization": f"Bearer {LI_TOKEN}"},
        data=image_bytes,
    )
    put.raise_for_status()
    log(f"Image uploaded → {asset_urn}")
    return asset_urn


# ── 4. Publish the post ───────────────────────────────────────────────────────
def create_post(post_data, asset_urn):
    headers = {
        "Authorization":             f"Bearer {LI_TOKEN}",
        "Content-Type":              "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    resp = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers=headers,
        json={
            "author":         LI_PERSON_URN,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary":    {"text": post_data["post_text"]},
                    "shareMediaCategory": "IMAGE",
                    "media": [{
                        "status": "READY",
                        "media":  asset_urn,
                        "title":  {"text": post_data.get("headline", f"Day {post_data['day']}")},
                    }],
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        },
    )
    resp.raise_for_status()
    post_urn = resp.json().get("id", "")
    log(f"Post published → {post_urn}")
    return post_urn


# ── 5. Add first comment ──────────────────────────────────────────────────────
def add_comment(post_urn, comment_text):
    encoded = urllib.parse.quote(post_urn, safe="")
    resp = requests.post(
        f"https://api.linkedin.com/v2/socialActions/{encoded}/comments",
        headers={
            "Authorization":             f"Bearer {LI_TOKEN}",
            "Content-Type":              "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        json={
            "actor":   LI_PERSON_URN,
            "message": {"text": comment_text},
        },
    )
    if resp.ok:
        log("First comment posted")
    else:
        log(f"Comment failed: {resp.status_code} {resp.text}")


# ── 6. Commit updated JSON back to repo ───────────────────────────────────────
def mark_posted(fpath, post_data):
    post_data["posted"] = True
    fpath.write_text(json.dumps(post_data, indent=2, ensure_ascii=False) + "\n")
    subprocess.run(["git", "config", "user.email", "action@github.com"], check=True)
    subprocess.run(["git", "config", "user.name",  "LinkedIn Bot"],      check=True)
    subprocess.run(["git", "add", str(fpath), str(LOG_FILE)],            check=True)
    subprocess.run(["git", "commit", "-m",
                    f"Mark day {post_data['day']} as posted [skip ci]"], check=True)
    subprocess.run(["git", "push"],                                       check=True)
    log(f"Day {post_data['day']} marked posted and committed")


# ── 7. Email notification ─────────────────────────────────────────────────────
def notify(post_data, post_urn):
    if not GMAIL_APP_PASSWORD:
        log("No GMAIL_APP_PASSWORD set — skipping email notification")
        return

    day  = post_data["day"]
    url  = post_data.get("dashboard_url", "")
    stat = post_data.get("key_stat", "")

    subject = f"✅ Day {day} posted to LinkedIn — From Memphis to 50 States"
    body = (
        f"Day {day} of 10 is live on LinkedIn.\n\n"
        f"Headline: {post_data.get('headline', '')}\n"
        f"Key stat: {stat}\n"
        f"Dashboard: {url}\n"
        f"LinkedIn post: https://www.linkedin.com/feed/update/{post_urn}/\n\n"
        f"Next post: Day {day + 1} tomorrow at 8am CST.\n"
        if day < 10 else
        f"Day {day} of 10 is live on LinkedIn.\n\n"
        f"Headline: {post_data.get('headline', '')}\n"
        f"Dashboard: {url}\n"
        f"LinkedIn post: https://www.linkedin.com/feed/update/{post_urn}/\n\n"
        f"That's all 10 days. Challenge complete.\n"
    )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = NOTIFY_EMAIL

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        log(f"Email notification sent to {NOTIFY_EMAIL}")
    except Exception as e:
        log(f"Email notification failed (non-fatal): {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    today = date.today().isoformat()
    log(f"=== Daily post run — {today} ===")

    fpath, post_data = load_todays_post()
    if not post_data:
        log(f"No post scheduled for {today}. Nothing to do.")
        sys.exit(0)

    day = post_data["day"]
    log(f"Posting Day {day}: {post_data.get('headline', '')}")

    if post_data.get("posted"):
        log(f"Day {day} already posted. Skipping.")
        sys.exit(0)

    try:
        image_bytes = load_image(post_data)
        asset_urn   = upload_image(image_bytes)
        post_urn    = create_post(post_data, asset_urn)

        log("Waiting 30 seconds before first comment...")
        time.sleep(30)
        add_comment(post_urn, post_data["first_comment"])

        mark_posted(fpath, post_data)
        notify(post_data, post_urn)
        log(f"Day {day} complete. ✓\n")

    except Exception as e:
        log(f"ERROR on Day {day}: {e}")
        raise


if __name__ == "__main__":
    main()
