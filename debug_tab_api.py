"""Debug script to see actual TAB API response"""
import asyncio
import httpx
import json

async def fetch_tab_data():
    url = "https://api.beta.tab.com.au/v1/tab-info-service/sports/Soccer/competitions/English%20Premier%20League/matches"
    params = {"jurisdiction": "VIC"}

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-AU,en;q=0.9",
        "Origin": "https://www.tab.com.au",
        "Referer": "https://www.tab.com.au/",
    }

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(url, headers=headers, params=params, timeout=30)
        data = response.json()

        print("=" * 80)
        print("FULL API RESPONSE:")
        print("=" * 80)
        print(json.dumps(data, indent=2)[:2000])  # First 2000 chars
        print("\n...")
        print("=" * 80)

        if data.get("matches"):
            print(f"\nFound {len(data['matches'])} matches")
            print("\nFIRST MATCH STRUCTURE:")
            print("=" * 80)
            print(json.dumps(data['matches'][0], indent=2))

if __name__ == "__main__":
    asyncio.run(fetch_tab_data())
