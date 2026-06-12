from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
from groq import Groq
import anthropic
import chromadb
from supabase import create_client
from dotenv import load_dotenv
import os, io, json, re

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

chroma_client = chromadb.PersistentClient(path="./chroma_db")
capability_collection = chroma_client.get_or_create_collection(name="capability_library")


@app.get("/")
def root():
    return {"status": "BidEngine Backend is running ✅"}


def extract_with_groq(text):
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": f"""Extract from this RFP and return ONLY valid JSON, no extra text:
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
{text[:4000]}"""
        }],
        max_tokens=2000,
    )
    raw = response.choices[0].message.content
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    try:
        return json.loads(match.group()) if match else {"raw": raw}
    except json.JSONDecodeError:
        return {"raw": raw}


def save_workspace(workspace_name, text, extracted):
    workspace = supabase.table("workspaces").insert({
        "name": workspace_name,
        "raw_text": text[:5000],
        "extracted_data": extracted,
        "status": "active"
    }).execute()
    return workspace.data[0]["id"]


def get_matching_capabilities(requirements):
    try:
        query = " ".join(requirements[:5])
        results = capability_collection.query(
            query_texts=[query],
            n_results=5
        )
        matches = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            matches.append(
                f"{meta['domain']} ({meta['year']}) - {meta['contract_value']} - {meta['client_type']}"
            )
        return matches
    except:
        return []


@app.post("/upload-rfp")
async def upload_rfp(file: UploadFile = File(...), workspace_name: str = "New RFP"):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    content = await file.read()
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read PDF: {str(e)}")

    if not text.strip():
        raise HTTPException(status_code=400, detail="No text found in the PDF")

    try:
        extracted = extract_with_groq(text)
        workspace_id = save_workspace(workspace_name, text, extracted)
    except Exception as e:
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

        workspace = result.data[0]
        extracted = workspace["extracted_data"]

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": f"""Generate compliance checklist and return ONLY valid JSON:
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
{json.dumps(extracted.get('requirements', []))}"""
            }],
            max_tokens=2000,
        )

        raw = response.choices[0].message.content
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

        workspace = result.data[0]
        extracted = workspace["extracted_data"]

        bid_data = supabase.table("bid_history").select("*").execute()
        wins = [b for b in bid_data.data if b["outcome"] == "Win"]
        total = len(bid_data.data)
        win_rate = round((len(wins) / total) * 100) if total > 0 else 0

        requirements = extracted.get("requirements", [])
        matching_caps = get_matching_capabilities(requirements)

        # Formula based consistent score
        score = 0
        history_score = 25 if win_rate > 60 else 10
        capability_score = 25 if len(matching_caps) >= 3 else (15 if len(matching_caps) >= 1 else 5)
        budget_score = 25 if extracted.get("budget") else 10
        requirements_score = 25 if len(requirements) > 0 else 10

        score = history_score + capability_score + budget_score + requirements_score

        criteria = [
            {"name": "Historical Win Rate", "score": history_score * 4, "reason": f"{win_rate}% past win rate"},
            {"name": "Capability Match", "score": capability_score * 4, "reason": f"{len(matching_caps)} matching projects found"},
            {"name": "Budget Clarity", "score": budget_score * 4, "reason": "Budget specified in RFP" if extracted.get("budget") else "Budget not specified"},
            {"name": "Requirements Clarity", "score": requirements_score * 4, "reason": f"{len(requirements)} requirements extracted"},
        ]

        decision = "GO" if score >= 60 else "NO-GO"
        recommendation = f"Based on {len(matching_caps)} matching past projects and {win_rate}% historical win rate, this bid is {'worth pursuing' if decision == 'GO' else 'high risk'}."

        supabase.table("win_scores").insert({
            "workspace_id": workspace_id,
            "score": score,
            "decision": decision,
            "criteria": json.dumps(criteria),
            "recommendation": recommendation
        }).execute()

        return {"success": True, "win_probability": {
            "overall_score": score,
            "decision": decision,
            "criteria": criteria,
            "recommendation": recommendation
        }}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-draft/{workspace_id}")
async def generate_draft(workspace_id: str):
    try:
        result = supabase.table("workspaces").select("*").eq("id", workspace_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Workspace not found")

        workspace = result.data[0]
        extracted = workspace["extracted_data"]

        # ChromaDB se matching projects nikalo
        requirements = extracted.get("requirements", [])
        matching_caps = get_matching_capabilities(requirements)

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": f"""Write a professional proposal and return ONLY valid JSON:
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

IMPORTANT: In Team & Experience section, explicitly mention these past projects by name:
{', '.join(matching_caps)}
Write like: "Based on our past project [project name], we have proven experience in..."""
            }],
            max_tokens=2000,
        )

        raw = response.choices[0].message.content
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        draft = json.loads(match.group()) if match else {"sections": []}

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
        data = result.data[0]
        criteria = []
        if data.get("criteria"):
            try:
                criteria = json.loads(data["criteria"]) if isinstance(data["criteria"], str) else data["criteria"]
            except:
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
@app.get("/stats")
async def get_stats():
    try:
        workspaces = supabase.table("workspaces").select("*").execute()
        capabilities = supabase.table("capability_library").select("*").execute()
        bid_history = supabase.table("bid_history").select("*").execute()
        wins = [b for b in bid_history.data if b["outcome"] == "Win"]
        win_rate = round((len(wins) / len(bid_history.data)) * 100) if bid_history.data else 0
        return {
            "totalBids": len(workspaces.data),
            "capabilities": len(capabilities.data),
            "winRate": win_rate
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/drafts/{workspace_id}")
async def get_drafts(workspace_id: str):
    try:
        result = supabase.table("drafts").select("*").eq("workspace_id", workspace_id).execute()
        sections = [{"title": d["section"], "content": d["content"]} for d in result.data]
        return {"sections": sections}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    