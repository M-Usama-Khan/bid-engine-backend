from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import google.generativeai as genai
import chromadb
from supabase import create_client
from dotenv import load_dotenv
from typing import Any, cast
import os, io, json, re

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

genai.configure(api_key=os.getenv("GEMINI_API_KEY") or "")
gemini = genai.GenerativeModel("gemini-1.5-flash")

supabase = create_client(
    os.getenv("SUPABASE_URL") or "",
    os.getenv("SUPABASE_KEY") or ""
)

chroma_client = chromadb.PersistentClient(path="./chroma_db")
capability_collection = chroma_client.get_or_create_collection(name="capability_library")


def call_gemini(prompt: str) -> str:
    response = gemini.generate_content(prompt)
    return response.text


@app.get("/")
def root():
    return {"status": "BidEngine Backend Chal Raha Hai ✅"}


@app.get("/health")
async def health_check():
    print("[HEALTH] Checking backend health...")
    try:
        print("[HEALTH] Checking Supabase connection...")
        supabase.table("workspaces").select("count").execute()
        print("[HEALTH] ✅ All services OK")
        return {
            "status": "healthy ✅",
            "supabase": "connected ✅",
            "gemini": "ready ✅"
        }
    except Exception as e:
        print(f"[HEALTH ERROR] {str(e)}")
        return {
            "status": "error ❌", 
            "detail": str(e),
            "supabase": "connection failed ❌"
        }


@app.get("/stats")
async def get_stats():
    try:
        print("[STATS] Fetching stats from Supabase...")
        caps = supabase.table("capability_library").select("*").execute()
        bids = supabase.table("bid_history").select("*").execute()
        print(f"[STATS] Success - capabilities: {len(caps.data)}, bids: {len(bids.data)}")
        return {
            "capabilities": len(caps.data),
            "total_bids": len(bids.data),
        }
    except Exception as e:
        print(f"[STATS ERROR] Failed to fetch: {str(e)}")
        return {
            "capabilities": 50, 
            "total_bids": 120,
            "error": "Using fallback values - database connection failed"
        }


def extract_with_gemini(text: str) -> dict:
    raw = call_gemini(f"""Extract from this RFP and return ONLY valid JSON, no extra text:
{{
    "requirements": ["requirement 1", "requirement 2"],
    "deadline": "submission deadline date",
    "budget": "total budget amount",
    "evaluation_criteria": [
        {{"criteria": "criteria name", "weight": "percentage or points"}}
    ],
    "summary": "2-3 line project summary"
}}

Document:
{text[:4000]}""")
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    try:
        return json.loads(match.group()) if match else {"raw": raw}
    except json.JSONDecodeError:
        return {"raw": raw}


def save_workspace(workspace_name: str, text: str, extracted: dict) -> str:
    workspace = supabase.table("workspaces").insert({
        "name": workspace_name,
        "raw_text": text[:5000],
        "extracted_data": extracted,
        "status": "active"
    }).execute()
    row = cast(dict, workspace.data[0])
    return str(row["id"])


def get_matching_capabilities(requirements: list) -> list:
    try:
        query = " ".join(requirements[:5])
        results = capability_collection.query(
            query_texts=[query],
            n_results=5
        )
        matches = []
        docs_res = results.get("documents")
        metas_res = results.get("metadatas")
        
        if not docs_res or not metas_res:
            return []
            
        docs: list = docs_res[0]
        metas: list = metas_res[0]
        for i, doc in enumerate(docs):
            meta = cast(dict, metas[i])
            matches.append(
                f"{meta['domain']} ({meta['year']}) - {meta['contract_value']} - {meta['client_type']}"
            )
        return matches
    except Exception:
        return []


@app.post("/upload-rfp")
async def upload_rfp(file: UploadFile = File(...), workspace_name: str = "New RFP"):
    filename = file.filename or ""
    print(f"[UPLOAD] Received file: {filename}, type: {file.content_type}")
    
    # Allow both PDF and DOCX files
    allowed_extensions = [".pdf", ".docx", ".doc"]
    file_ext = "." + filename.split(".")[-1].lower() if "." in filename else ""
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Only PDF and DOCX files are allowed. Got: {file_ext if file_ext else 'no extension'}"
        )

    content = await file.read()
    text = ""
    try:
        if file_ext.lower() == ".pdf":
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
        elif file_ext.lower() in [".docx", ".doc"]:
            # For DOCX files, we'll extract text using python-docx if available
            # For now, return error message asking to use PDF or suggesting conversion
            raise HTTPException(
                status_code=400,
                detail="DOCX support coming soon. Please convert to PDF first."
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] PDF reading failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Could not read file: {str(e)}")

    if not text.strip():
        raise HTTPException(status_code=400, detail="No text found in file")

    try:
        print(f"[EXTRACT] Extracting data with Gemini...")
        extracted = extract_with_gemini(text)
        print(f"[SAVE] Saving workspace...")
        workspace_id = save_workspace(workspace_name, text, extracted)
        print(f"[SUCCESS] Workspace created: {workspace_id}")
    except Exception as e:
        print(f"[ERROR] Failed to save workspace: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "success": True,
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "extracted_data": extracted
    }


@app.post("/generate-checklist/{workspace_id}")
async def generate_checklist(workspace_id: str):
    try:
        result = supabase.table("workspaces").select("*").eq("id", workspace_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Workspace not found")

        workspace = cast(dict, result.data[0])
        extracted = cast(dict, workspace["extracted_data"])

        raw = call_gemini(f"""Generate compliance checklist and return ONLY valid JSON:
{{
    "checklist": [
        {{
            "requirement": "requirement text",
            "status": "pass",
            "notes": "short note"
        }}
    ]
}}

Status must be exactly: pass, fail, or partial
Requirements:
{json.dumps(extracted.get('requirements', []))}""")

        match = re.search(r'\{.*\}', raw, re.DOTALL)
        checklist = json.loads(match.group()) if match else {"checklist": []}

        for item in checklist.get("checklist", []):
            supabase.table("requirements").insert({
                "workspace_id": workspace_id,
                "requirement": item["requirement"],
                "compliance_status": item["status"]
            }).execute()

        return {"success": True, "checklist": checklist}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/win-probability/{workspace_id}")
async def win_probability(workspace_id: str):
    try:
        result = supabase.table("workspaces").select("*").eq("id", workspace_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Workspace not found")

        workspace = cast(dict, result.data[0])
        extracted = cast(dict, workspace["extracted_data"])

        bid_data = supabase.table("bid_history").select("*").execute()
        wins = [b for b in bid_data.data if cast(dict, b)["outcome"] == "Win"]
        total = len(bid_data.data)
        win_rate = round((len(wins) / total) * 100) if total > 0 else 0

        requirements: list = extracted.get("requirements", [])
        matching_caps = get_matching_capabilities(requirements)

        raw = call_gemini(f"""Calculate win probability and return ONLY this exact JSON format, no markdown, no extra text:
{{"overall_score": 75, "decision": "GO", "criteria": [{{"name": "Budget Alignment", "score": 80, "reason": "good fit"}}, {{"name": "Technical Fit", "score": 70, "reason": "strong match"}}, {{"name": "Competition Level", "score": 60, "reason": "moderate"}}, {{"name": "Experience Match", "score": 85, "reason": "excellent"}}], "recommendation": "Strong bid opportunity worth pursuing"}}

Use this data to calculate REAL scores (overall_score must be integer 0-100, decision must be GO if score>=60 else NO-GO):
RFP: {json.dumps(extracted)}
Historical Win Rate: {win_rate}%
Matching Past Projects: {', '.join(matching_caps)}""")

        match = re.search(r'\{.*\}', raw, re.DOTALL)
        try:
            scores: dict = json.loads(match.group()) if match else {}
        except Exception:
            scores = {}

        if not scores.get("overall_score"):
            scores["overall_score"] = win_rate
        if not scores.get("decision"):
            scores["decision"] = "GO" if win_rate >= 60 else "NO-GO"

        supabase.table("win_scores").insert({
            "workspace_id": workspace_id,
            "score": scores.get("overall_score", 0),
            "decision": scores.get("decision", "NO-GO"),
            "criteria": json.dumps(scores.get("criteria", [])),
            "recommendation": scores.get("recommendation", "")
        }).execute()

        return {"success": True, "win_probability": scores}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-draft/{workspace_id}")
async def generate_draft(workspace_id: str):
    try:
        result = supabase.table("workspaces").select("*").eq("id", workspace_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Workspace not found")

        workspace = cast(dict, result.data[0])
        extracted = cast(dict, workspace["extracted_data"])

        requirements: list = extracted.get("requirements", [])
        matching_caps = get_matching_capabilities(requirements)

        raw = call_gemini(f"""Write a professional proposal and return ONLY valid JSON:
{{
    "sections": [
        {{"title": "Executive Summary", "content": "detailed content here"}},
        {{"title": "Technical Approach", "content": "detailed content here"}},
        {{"title": "Team & Experience", "content": "detailed content here"}},
        {{"title": "Timeline & Deliverables", "content": "detailed content here"}},
        {{"title": "Compliance Statement", "content": "detailed content here"}},
        {{"title": "Budget & Pricing", "content": "detailed content here"}}
    ]
}}

RFP Data: {json.dumps(extracted)}
Our Relevant Past Projects: {', '.join(matching_caps)}

Use past projects as evidence in Team & Experience section.""")

        match = re.search(r'\{.*\}', raw, re.DOTALL)
        draft: dict = json.loads(match.group()) if match else {"sections": []}

        for section in draft.get("sections", []):
            supabase.table("drafts").insert({
                "workspace_id": workspace_id,
                "section": section["title"],
                "content": section["content"]
            }).execute()

        return {"success": True, "draft": draft}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workspaces")
async def get_workspaces():
    try:
        result = supabase.table("workspaces").select("*").order("created_at", desc=True).execute()
        return {"success": True, "workspaces": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str):
    try:
        result = supabase.table("workspaces").select("*").eq("id", workspace_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return {"success": True, "workspace": result.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.delete("/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: str):
    try:
        supabase.table("workspaces").delete().eq("id", workspace_id).execute()
        return {"success": True, "message": "Workspace deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/win-scores/{workspace_id}")
async def get_win_scores(workspace_id: str):
    try:
        result = supabase.table("win_scores").select("*").eq("workspace_id", workspace_id).execute()
        if not result.data:
            return {"win_probability": {}}
        data = cast(dict, result.data[0])
        criteria: list = []
        if data.get("criteria"):
            try:
                raw_criteria = data["criteria"]
                criteria = json.loads(raw_criteria) if isinstance(raw_criteria, str) else raw_criteria
            except Exception:
                criteria = []
        return {
            "win_probability": {
                "overall_score": data.get("score", 0),
                "decision": data.get("decision", "NO-GO"),
                "criteria": criteria,
                "recommendation": data.get("recommendation", "")
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/drafts/{workspace_id}")
async def get_drafts(workspace_id: str):
    try:
        result = supabase.table("drafts").select("*").eq("workspace_id", workspace_id).execute()
        sections = [{"title": cast(dict, d)["section"], "content": cast(dict, d)["content"]} for d in result.data]
        return {"sections": sections}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))