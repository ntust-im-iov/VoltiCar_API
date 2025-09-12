from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Optional
import os
import hmac
import hashlib
import json
import httpx # Added httpx for making HTTP requests
import datetime # Added datetime for timestamp in embed

router = APIRouter()

GITHUB_WEBHOOK_SECRET: Optional[str] = os.environ.get("GITHUB_WEBHOOK_SECRET")
DISCORD_BOT_TOKEN: Optional[str] = os.environ.get("DISCORD_BOT_TOKEN")
DISCORD_API_BASE_URL: str = "https://discord.com/api/v10"

async def verify_github_signature(request: Request) -> bool:
    """Verify the GitHub webhook signature."""
    signature = request.headers.get('X-Hub-Signature')
    if not signature:
        return False

    try:
        body = await request.body()
        expected_signature = hmac.new(
            GITHUB_WEBHOOK_SECRET.encode('utf-8'),
            body,
            hashlib.sha1
        ).hexdigest()
        return hmac.compare_digest(f"sha1={expected_signature}", signature)
    except Exception as e:
        print(f"Signature verification error: {e}")
        return False

def get_thread_id_from_database(issue_number: int) -> Optional[str]:
    """Get thread_id from database using issue_number by checking 'issue_number' field in mapping."""
    try:
        # Specify encoding for consistency, though default is often utf-8
        with open("data/user_github_mappings.json", "r", encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: data/user_github_mappings.json not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: data/user_github_mappings.json is not valid JSON.")
        return None
        
    for thread_id_key, mapping_data in data.items():
        if isinstance(mapping_data, dict):
            # Check if 'issue_number' field exists in the mapping_data and matches the input issue_number
            if mapping_data.get("issue_number") == str(issue_number):
                return thread_id_key # The key of the JSON object is assumed to be the thread_id
    return None

async def call_sync_github_comment(author: str, content: str, url: str, thread_id: str):
    """Sends an embed message to a Discord thread同步 GitHub 留言."""
    if not DISCORD_BOT_TOKEN:
        print("DISCORD_BOT_TOKEN not configured. Skipping Discord notification.")
        return

    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    embed = {
        "title": f"New GitHub Comment by {author}",
        "description": content,
        "url": url,
        "color": 0x00FFFF,  # Cyan color
        "footer": {"text": "Synced from GitHub"},
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    payload = {"embeds": [embed]}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{DISCORD_API_BASE_URL}/channels/{thread_id}/messages", headers=headers, json=payload)
            response.raise_for_status()  # Raise an exception for bad status codes
            print(f"Successfully sent GitHub comment to Discord thread {thread_id}.")
        except httpx.HTTPStatusError as e:
            print(f"Error sending GitHub comment to Discord: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"An unexpected error occurred while sending GitHub comment to Discord: {e}")

async def call_archive_dev_thread(thread_id: str):
    """Archives a Discord development thread and sends a closing message."""
    if not DISCORD_BOT_TOKEN:
        print("DISCORD_BOT_TOKEN not configured. Skipping Discord thread archival.")
        return

    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 1. Send a closing message (optional, but good practice)
    closing_message_payload = {
        "content": "This development thread has been closed and archived as the corresponding GitHub issue was closed."
    }
    async with httpx.AsyncClient() as client:
        try:
            await client.post(f"{DISCORD_API_BASE_URL}/channels/{thread_id}/messages", headers=headers, json=closing_message_payload)
            print(f"Sent closing message to Discord thread {thread_id}.")
        except Exception as e:
            print(f"Error sending closing message to Discord thread {thread_id}: {e}")

        # 2. Archive the thread
        archive_payload = {"archived": True}
        try:
            response = await client.patch(f"{DISCORD_API_BASE_URL}/channels/{thread_id}", headers=headers, json=archive_payload)
            response.raise_for_status()
            print(f"Successfully archived Discord thread {thread_id}.")
        except httpx.HTTPStatusError as e:
            print(f"Error archiving Discord thread: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"An unexpected error occurred while archiving Discord thread: {e}")

@router.post("/webhook", summary="接收 GitHub Webhook 通知")
async def github_webhook(request: Request):
    """
    此端點用於接收來自 GitHub 的 Webhook 事件通知，並根據事件類型觸發相應的 Discord Bot 操作。
    - **簽名驗證**: 會使用 `GITHUB_WEBHOOK_SECRET` 環境變數來驗證請求的簽名，確保請求來自 GitHub。
    - **事件處理**:
        - `issue_comment`: 當 GitHub Issue 有新留言時，會將該留言同步到對應的 Discord 開發討論串中。
        - `issues` (action: `closed`): 當 GitHub Issue 被關閉時，會自動將對應的 Discord 開發討論串封存。
    """

    if not GITHUB_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="GitHub webhook secret not configured.")
    
    # Check for DISCORD_BOT_TOKEN at the beginning of the webhook processing
    # If critical for operation, you might raise HTTPException here too,
    # or let the individual functions handle its absence.
    if not DISCORD_BOT_TOKEN:
        print("Warning: DISCORD_BOT_TOKEN is not configured. Discord integrations will be skipped.")
        # Depending on requirements, you might want to raise an error:
        # raise HTTPException(status_code=500, detail="Discord Bot Token not configured.")

    if not await verify_github_signature(request):
        raise HTTPException(status_code=401, detail="Invalid GitHub signature.")

    payload = await request.json()
    print(f"Received GitHub webhook payload: {payload}")

    # Process the webhook payload based on event type
    event = request.headers.get('X-GitHub-Event')
    if event == "ping":
        return {"message": "Pong!"}
    elif event == "issue_comment":
        # Handle issue comment event
        comment = payload["comment"]
        author = comment["user"]["login"]
        content = comment["body"]
        url = comment["html_url"]
        issue_number = payload["issue"]["number"]

        thread_id = get_thread_id_from_database(issue_number)
        if thread_id:
            await call_sync_github_comment(author, content, url, thread_id)
        else:
            print(f"No thread_id found for issue_number: {issue_number}")

    elif event == "issues":
        # Handle issue event (e.g., issue closed)
        action = payload.get("action")
        if action == "closed":
            issue_number = payload["issue"]["number"]
            thread_id = get_thread_id_from_database(issue_number)
            if thread_id:
                await call_archive_dev_thread(thread_id)
            else:
                print(f"No thread_id found for issue_number: {issue_number}")

    return {"message": "Webhook received and processing"}
