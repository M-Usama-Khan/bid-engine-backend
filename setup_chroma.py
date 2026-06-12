from supabase import create_client
from dotenv import load_dotenv
import os
import chromadb

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# ChromaDB setup
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Collection banao
collection = chroma_client.get_or_create_collection(
    name="capability_library"
)

# Supabase se 50 projects lo
cap_data = supabase.table("capability_library").select("*").execute()

# ChromaDB mein store karo
for cap in cap_data.data:
    collection.upsert(
        ids=[cap["cap_id"]],
        documents=[f"{cap['domain']} - {cap['project_summary']} - {cap['certification']} - {cap['client_type']}"],
        metadatas=[{
            "domain": cap["domain"],
            "certification": cap["certification"],
            "year": str(cap["year_completed"]),
            "contract_value": cap["contract_value"],
            "client_type": cap["client_type"]
        }]
    )

print(f"✅ {len(cap_data.data)} projects ChromaDB mein load ho gaye!")