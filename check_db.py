"""
check_db.py — Quick utility to inspect what's stored in Weaviate Cloud
Run: python check_db.py
"""
import weaviate
from weaviate.auth import AuthApiKey
from collections import Counter

from config import WEAVIATE_URL, WEAVIATE_API_KEY, WEAVIATE_COLLECTION

def main():
    print(f"\n{'='*60}")
    print(f"  Connecting to Weaviate Cloud...")
    print(f"  URL: {WEAVIATE_URL}")
    print(f"{'='*60}\n")

    # Connect to Weaviate Cloud
    client = weaviate.connect_to_weaviate_cloud(
        cluster_url=WEAVIATE_URL,
        auth_credentials=AuthApiKey(WEAVIATE_API_KEY),
    )

    try:
        # 1. Check connection
        if client.is_ready():
            print("✅ Connected to Weaviate Cloud!\n")
        else:
            print("❌ Weaviate is NOT ready.")
            return

        # 2. List all collections
        print("📦 Collections in your DB:")
        collections = client.collections.list_all()
        if not collections:
            print("  ⚠️  No collections found. Run main.py first to ingest documents.")
            return
        for name in collections:
            print(f"  - {name}")

        # 3. Count documents in our collection
        print(f"\n📊 Documents in '{WEAVIATE_COLLECTION}':")
        try:
            collection = client.collections.get(WEAVIATE_COLLECTION)
            total = collection.aggregate.over_all(total_count=True).total_count
            print(f"  Total documents: {total}")
        except Exception as e:
            print(f"  ⚠️  Collection '{WEAVIATE_COLLECTION}' not found: {e}")
            print("  Run main.py first to ingest documents.")
            return

        # 4. Show sample documents (first 5)
        print(f"\n📄 Sample documents (first 5):")
        response = collection.query.fetch_objects(limit=5)
        for i, obj in enumerate(response.objects, 1):
            props = obj.properties
            source = props.get("source", "?")
            content_preview = str(props.get("content", ""))[:100].replace("\n", " ")
            print(f"\n  [{i}] Source: {source}")
            print(f"       Preview: {content_preview}...")

        # 5. Breakdown by source
        print(f"\n📈 Breakdown by source (sample):")
        response_all = collection.query.fetch_objects(limit=500)
        sources = Counter(
            obj.properties.get("source", "unknown")
            for obj in response_all.objects
        )
        for src, count in sorted(sources.items()):
            print(f"  {src:<25}: {count} docs")

    finally:
        client.close()
        print(f"\n{'='*60}")
        print("  Connection closed.")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
