from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Bid History Data
bid_history = [
    {"bid_id": "BID-0001", "client": "FWO", "sector": "Construction", "budget": "PKR 22M", "score": 92, "outcome": "Win", "response_time": 94, "compliance_pct": 75, "doc_pages": 144, "gaps_found": 2, "bid_manager": "Sara Malik", "submission_date": "2025-02-22"},
    {"bid_id": "BID-0002", "client": "NLC", "sector": "Construction", "budget": "PKR 312M", "score": 72, "outcome": "Win", "response_time": 32, "compliance_pct": 61, "doc_pages": 77, "gaps_found": 3, "bid_manager": "Usman Raza", "submission_date": "2025-04-30"},
    {"bid_id": "BID-0003", "client": "PIMS", "sector": "IT Services", "budget": "PKR 297M", "score": 57, "outcome": "Loss", "response_time": 163, "compliance_pct": 86, "doc_pages": 142, "gaps_found": 7, "bid_manager": "Nadia Ahmed", "submission_date": "2025-10-29"},
    {"bid_id": "BID-0004", "client": "OGDCL", "sector": "Energy", "budget": "PKR 424M", "score": 45, "outcome": "Loss", "response_time": 64, "compliance_pct": 87, "doc_pages": 204, "gaps_found": 4, "bid_manager": "Bilal Sheikh", "submission_date": "2025-03-21"},
    {"bid_id": "BID-0005", "client": "HEC", "sector": "Healthcare", "budget": "PKR 500M", "score": 93, "outcome": "Win", "response_time": 110, "compliance_pct": 66, "doc_pages": 77, "gaps_found": 6, "bid_manager": "Hira Noor", "submission_date": "2025-02-19"},
    {"bid_id": "BID-0006", "client": "Jazz", "sector": "Education", "budget": "PKR 443M", "score": 67, "outcome": "Loss", "response_time": 91, "compliance_pct": 62, "doc_pages": 403, "gaps_found": 7, "bid_manager": "Tariq Mehmood", "submission_date": "2025-10-02"},
    {"bid_id": "BID-0007", "client": "SBP", "sector": "Construction", "budget": "PKR 482M", "score": 69, "outcome": "Loss", "response_time": 44, "compliance_pct": 95, "doc_pages": 180, "gaps_found": 5, "bid_manager": "Zara Hussain", "submission_date": "2025-10-23"},
    {"bid_id": "BID-0008", "client": "WAPDA", "sector": "Healthcare", "budget": "PKR 370M", "score": 49, "outcome": "Loss", "response_time": 35, "compliance_pct": 74, "doc_pages": 425, "gaps_found": 4, "bid_manager": "Kamran Ali", "submission_date": "2025-02-10"},
    {"bid_id": "BID-0009", "client": "CDA", "sector": "Healthcare", "budget": "PKR 453M", "score": 51, "outcome": "Loss", "response_time": 121, "compliance_pct": 77, "doc_pages": 262, "gaps_found": 5, "bid_manager": "Faiza Iqbal", "submission_date": "2025-03-25"},
    {"bid_id": "BID-0010", "client": "PIA", "sector": "Education", "budget": "PKR 191M", "score": 58, "outcome": "Loss", "response_time": 92, "compliance_pct": 64, "doc_pages": 341, "gaps_found": 2, "bid_manager": "Asif Khan", "submission_date": "2025-10-01"},
]

# Capability Library Data
capability_library = [
    {"cap_id": "CAP-001", "domain": "Cybersecurity", "project_summary": "Cybersecurity deployment for client", "certification": "ISO 27001", "year_completed": 2023, "contract_value": "PKR 15M", "duration_months": 34, "client_type": "International"},
    {"cap_id": "CAP-002", "domain": "ERP Implementation", "project_summary": "ERP Implementation deployment for client", "certification": "N/A", "year_completed": 2021, "contract_value": "PKR 159M", "duration_months": 14, "client_type": "Federal Govt"},
    {"cap_id": "CAP-003", "domain": "Road Construction", "project_summary": "Road Construction deployment for client", "certification": "ISO 27001", "year_completed": 2020, "contract_value": "PKR 177M", "duration_months": 32, "client_type": "Federal Govt"},
    {"cap_id": "CAP-004", "domain": "Bridge Engineering", "project_summary": "Bridge Engineering deployment for client", "certification": "N/A", "year_completed": 2025, "contract_value": "PKR 73M", "duration_months": 24, "client_type": "Federal Govt"},
    {"cap_id": "CAP-005", "domain": "Fleet Management", "project_summary": "Fleet Management deployment for client", "certification": "PMP", "year_completed": 2022, "contract_value": "PKR 137M", "duration_months": 26, "client_type": "International"},
    {"cap_id": "CAP-006", "domain": "Hospital IT", "project_summary": "Hospital IT deployment for client", "certification": "CMMI L3", "year_completed": 2020, "contract_value": "PKR 154M", "duration_months": 19, "client_type": "International"},
    {"cap_id": "CAP-007", "domain": "Medical Equipment", "project_summary": "Medical Equipment deployment for client", "certification": "ISO 27001", "year_completed": 2022, "contract_value": "PKR 94M", "duration_months": 19, "client_type": "Private Sector"},
    {"cap_id": "CAP-008", "domain": "Solar Energy", "project_summary": "Solar Energy deployment for client", "certification": "CMMI L3", "year_completed": 2024, "contract_value": "PKR 31M", "duration_months": 33, "client_type": "Provincial Govt"},
    {"cap_id": "CAP-009", "domain": "Network Design", "project_summary": "Network Design deployment for client", "certification": "CMMI L3", "year_completed": 2022, "contract_value": "PKR 182M", "duration_months": 21, "client_type": "Private Sector"},
    {"cap_id": "CAP-010", "domain": "LMS Development", "project_summary": "LMS Development deployment for client", "certification": "N/A", "year_completed": 2022, "contract_value": "PKR 199M", "duration_months": 23, "client_type": "Federal Govt"},
]

# Insert data
print("Bid History loading...")
supabase.table("bid_history").insert(bid_history).execute()
print("✅ Bid History loaded!")

print("Capability Library loading...")
supabase.table("capability_library").insert(capability_library).execute()
print("✅ Capability Library loaded!")

print("🎉 All data loaded!")