"""
LinkedIn daily posting automation — From Memphis to 50 States challenge.

Image strategy:
  1. Canva API (brand template autofill) — if CANVA_API_TOKEN + CANVA_TEMPLATE_ID set
  2. Playwright screenshot of the live dashboard — automatic fallback

Finds the next un-posted day from posts/dayN.json, posts it, marks it done,
commits the updated JSON back to the repo.
"""
import json
import os
import sys
import time
import glob
import subprocess
import urllib.parse
from pathlib import Path

import requests

# ── Credentials from environment ──────────────────────────────────────────────
LI_TOKEN      = os.environ["LINKEDIN_ACCESS_TOKEN"]
LI_PERSON_URN = os.environ["LINKEDIN_PERSON_URN"]
CANVA_TOKEN   = os.environ.get("CANVA_API_TOKEN", "")
CANVA_TMPL_ID = os.environ.get("CANVA_TEMPLATE_ID", "")


# ── 1. Find the next unposted day ─────────────────────────────────────────────
def load_next_post():
    repo_root = Path(__file__).parent.parent
    files = sorted(repo_root.glob("posts/day*.json"))
    for fpath in files:
        data = json.loads(fpath.read_text())
        if not data.get("posted", False):
            return fpath, data
    return None, None


# ── 2a. Image via Canva brand-template autofill ───────────────────────────────
def canva_image(post_data):
    """
    Fills a Canva brand template with day-specific text and exports as PNG.
    Requires CANVA_API_TOKEN + CANVA_TEMPLATE_ID set as secrets.
    Create the template at canva.com → Brand Kit → Templates, mark text fields
    as auto-fill fields named: {headline}, {stat}, {day_tag}, {source}.
    """
    if not CANVA_TOKEN or not CANVA_TMPL_ID:
        return None

    headers = {
        "Authorization": f"Bearer {CANVA_TOKEN}",
        "Content-Type": "application/json",
    }

    # Extract a short headline and stat from first two lines of post_text
    lines = [l.strip() for l in post_data["post_text"].split("\n") if l.strip()]
    headline = lines[0][:120] if lines else f"Day {post_data['day']}"
    stat_line = lines[1][:80] if len(lines) > 1 else ""
    day_tag   = f"Day {post_data['day']} of 10 · From Memphis to 50 States"
    source    = "Source: government open data · mahendraaarumalla.github.io"

    # Autofill the brand template
    autofill_resp = requests.post(
        f"https://api.canva.com/rest/v1/brand-templates/{CANVA_TMPL_ID}/autofill",
        headers=headers,
        json={
            "title":  f"Memphis Education Day {post_data['day']}",
            "data": {
                "headline":  {"type": "text", "text": headline},
                "stat":      {"type": "text", "text": stat_line},
                "day_tag":   {"type": "text", "text": day_tag},
                "source":    {"type": "text", "text": source},
            },
        },
    )
    if autofill_resp.status_code != 200:
        print(f"[canva] autofill failed: {autofill_resp.status_code} {autofill_resp.text}")
        return None

    job = autofill_resp.json().get("job", {})
    design_id = None

    # Poll until the autofill job completes
    for _ in range(30):
        time.sleep(2)
        status_resp = requests.get(
            f"https://api.canva.com/rest/v1/brand-templates/{CANVA_TMPL_ID}/autofill/{job['id']}",
            headers=headers,
        )
        status = status_resp.json().get("job", {})
        if status.get("status") == "success":
            design_id = status["result"]["design"]["id"]
            break
        if status.get("status") == "failed":
            print("[canva] autofill job failed")
            return None

    if not design_id:
        print("[canva] timed out waiting for autofill")
        return None

    # Export the design as PNG
    export_resp = requests.post(
        "https://api.canva.com/rest/v1/exports",
        headers=headers,
        json={
            "design_id": design_id,
            "format":    "png",
            "width":     1200,
            "height":    628,
        },
    )
    if export_resp.status_code != 200:
        print(f"[canva] export failed: {export_resp.status_code}")
        return None

    export_job_id = export_resp.json().get("job", {}).get("id")

    # Poll export job
    for _ in range(30):
        time.sleep(2)
        poll = requests.get(
            f"https://api.canva.com/rest/v1/exports/{export_job_id}",
            headers=headers,
        )
        job_data = poll.json().get("job", {})
        if job_data.get("status") == "success":
            url = job_data["urls"][0]
            return requests.get(url).content
        if job_data.get("status") == "failed":
            print("[canva] export job failed")
            return None

    print("[canva] export timed out")
    return None


# ── 2b. Image via Playwright screenshot (reliable fallback) ───────────────────
def screenshot_image(dashboard_url):
    from playwright.sync_api import sync_playwright

    print(f"[playwright] screenshotting {dashboard_url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1200, "height": 628})
        page.goto(dashboard_url, wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(2500)    # let chart animations finish
        img = page.screenshot(type="png", clip={"x": 0, "y": 0, "width": 1200, "height": 628})
        browser.close()
    return img


# ── 3. Upload image to LinkedIn ───────────────────────────────────────────────
def upload_image(image_bytes):
    headers = {
        "Authorization":             f"Bearer {LI_TOKEN}",
        "Content-Type":              "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # Register upload slot
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

    # Upload the bytes
    put = requests.put(
        upload_url,
        headers={"Authorization": f"Bearer {LI_TOKEN}"},
        data=image_bytes,
    )
    put.raise_for_status()
    print(f"[linkedin] image uploaded → {asset_urn}")
    return asset_urn


# ── 4. Create the ugcPost ─────────────────────────────────────────────────────
def create_post(post_data, asset_urn):
    headers = {
        "Authorization":             f"Bearer {LI_TOKEN}",
        "Content-Type":              "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    payload = {
        "author":         LI_PERSON_URN,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary":    {"text": post_data["post_text"]},
                "shareMediaCategory": "IMAGE",
                "media": [{
                    "status": "READY",
                    "media":  asset_urn,
                    "title":  {"text": f"Day {post_data['day']} — From Memphis to 50 States"},
                }],
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }
    resp = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers=headers,
        json=payload,
    )
    resp.raise_for_status()
    post_id = resp.json().get("id", "")
    print(f"[linkedin] post published → {post_id}")
    return post_id


# ── 5. Add first comment ──────────────────────────────────────────────────────
def add_comment(post_urn, comment_text):
    encoded = urllib.parse.quote(post_urn, safe="")
    headers = {
        "Authorization":             f"Bearer {LI_TOKEN}",
        "Content-Type":              "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    resp = requests.post(
        f"https://api.linkedin.com/v2/socialActions/{encoded}/comments",
        headers=headers,
        json={
            "actor":   LI_PERSON_URN,
            "message": {"text": comment_text},
        },
    )
    if resp.ok:
        print("[linkedin] first comment posted")
    else:
        print(f"[linkedin] comment failed: {resp.status_code} {resp.text}")


# ── 6. Mark day as posted and commit ─────────────────────────────────────────
def mark_posted(fpath, post_data):
    post_data["posted"] = True
    fpath.write_text(json.dumps(post_data, indent=2, ensure_ascii=False))

    subprocess.run(["git", "config", "user.email", "action@github.com"], check=True)
    subprocess.run(["git", "config", "user.name",  "LinkedIn Bot"],      check=True)
    subprocess.run(["git", "add", str(fpath)],                           check=True)
    subprocess.run(["git", "commit", "-m",
                    f"Mark day {post_data['day']} as posted [skip ci]"], check=True)
    subprocess.run(["git", "push"],                                       check=True)
    print(f"[git] committed day {post_data['day']} as posted")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    fpath, post_data = load_next_post()
    if not post_data:
        print("All days are posted. Nothing to do.")
        sys.exit(0)

    day = post_data["day"]
    print(f"\n{'='*50}")
    print(f"  Posting Day {day} of 10")
    print(f"{'='*50}\n")

    # Generate image — Canva first, screenshot fallback
    image_bytes = canva_image(post_data)
    if not image_bytes:
        if CANVA_TOKEN and CANVA_TMPL_ID:
            print("[canva] failed — falling back to screenshot")
        else:
            print("[image] using Playwright screenshot (set CANVA_API_TOKEN + CANVA_TEMPLATE_ID to use Canva)")
        image_bytes = screenshot_image(post_data["dashboard_url"])

    # Upload, post, comment
    asset_urn = upload_image(image_bytes)
    post_urn  = create_post(post_data, asset_urn)

    if post_data.get("first_comment") and post_urn:
        time.sleep(3)   # brief pause before commenting
        add_comment(post_urn, post_data["first_comment"])

    # Mark done
    mark_posted(fpath, post_data)
    print(f"\nDay {day} published successfully.\n")


if __name__ == "__main__":
    main()
