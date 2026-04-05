import os
import sys

# Add ms_ai to path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from ms_ai.app.user_interactions import user_interaction_manager
    from ms_ai.app.vectordb import get_chroma_collection

    print("=" * 60)
    print("CHROMADB DIAGNOSTICS")
    print("=" * 60)

    # 1. Verify Chroma client
    print("\n1️⃣  CHROMA CLIENT")
    try:
        collection = get_chroma_collection()
        print(f"✅ Collection obtained: {collection.name}")
        print(f"✅ Total documents: {collection.count()}")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # 2. List all collections
    print("\n2️⃣  ALL COLLECTIONS")
    try:
        client = collection.client
        all_collections = client.list_collections()
        print(f"Total collections: {len(all_collections)}")
        for col in all_collections:
            print(f"  - {col.name} ({col.count()} documents)")
    except Exception as e:
        print(f"❌ Error: {e}")

    # 3. Inspect user_interactions metadata
    print("\n3️⃣  DOCUMENTS IN user_interactions")
    try:
        results = collection.get(include=["documents", "metadatas", "embeddings"])
        print(f"Total documents: {len(results['ids'])}")

        if results["ids"]:
            print("\n📄 First 3 IDs:")
            for i, id in enumerate(results["ids"][:3]):
                print(f"  {i+1}. {id}")
                if i < len(results["metadatas"]):
                    print(f"     Metadata: {results['metadatas'][i]}")
        else:
            print("⚠️  No documents in the collection")
    except Exception as e:
        print(f"❌ Error: {e}")

    # 4. Verify user_interaction_manager
    print("\n4️⃣  USER INTERACTION MANAGER")
    try:
        # Try retrieving interactions for a test user
        interactions = user_interaction_manager.get_user_interactions(
            user_login="test_user", limit=5
        )
        print("✅ Manager working")
        print(f"   Interactions found: {len(interactions)}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # 5. System information
    print("\n5️⃣  SYSTEM INFORMATION")
    chroma_path = "./chroma_data"
    if os.path.exists(chroma_path):
        size = sum(
            os.path.getsize(os.path.join(dirpath, filename))
            for dirpath, dirnames, filenames in os.walk(chroma_path)
            for filename in filenames
        ) / (1024 * 1024)
        print(f"✅ Chroma directory exists: {chroma_path}")
        print(f"   Size: {size:.2f} MB")
    else:
        print(f"⚠️  Chroma directory does not exist: {chroma_path}")

    print("\n" + "=" * 60)

except Exception as e:
    print(f"❌ FATAL ERROR: {e}")
    import traceback

    traceback.print_exc()
