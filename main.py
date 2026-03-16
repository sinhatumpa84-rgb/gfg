from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import sqlite3
import json
import os
from typing import List, Dict, Any
import google.generativeai as genai
from datetime import datetime
import io
import tempfile

# Initialize FastAPI app
app = FastAPI(title="AI-BI Dashboard API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your-api-key-here")
genai.configure(api_key=GEMINI_API_KEY)

# Database setup
DB_PATH = "dashboard.db"

class NaturalQuery(BaseModel):
    query: str
    conversation_history: List[Dict[str, str]] = []

class DashboardResponse(BaseModel):
    query: str
    charts: List[Dict[str, Any]]
    insights: List[str]
    error: str = None

class DatabaseSchema(BaseModel):
    tables: List[str]
    columns: Dict[str, List[str]]

# ==================== DATABASE FUNCTIONS ====================

def init_database():
    """Initialize SQLite database with sample data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY,
            date TEXT,
            region TEXT,
            product_category TEXT,
            revenue REAL,
            units_sold INTEGER,
            quarter TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            name TEXT,
            department TEXT,
            salary REAL,
            hire_date TEXT,
            region TEXT
        )
    ''')
    
    # Insert sample data
    sample_data = [
        ("2024-01-15", "North", "Electronics", 45000, 150, "Q1"),
        ("2024-02-20", "South", "Furniture", 32000, 80, "Q1"),
        ("2024-03-10", "East", "Clothing", 28000, 200, "Q1"),
        ("2024-04-05", "West", "Electronics", 55000, 180, "Q2"),
        ("2024-05-15", "North", "Furniture", 38000, 95, "Q2"),
        ("2024-06-20", "South", "Clothing", 42000, 240, "Q2"),
        ("2024-07-10", "East", "Electronics", 61000, 200, "Q3"),
        ("2024-08-15", "West", "Furniture", 35000, 85, "Q3"),
        ("2024-09-20", "North", "Clothing", 48000, 260, "Q3"),
        ("2024-10-05", "South", "Electronics", 52000, 170, "Q4"),
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO sales VALUES (NULL, ?, ?, ?, ?, ?, ?)',
        sample_data
    )
    
    employee_data = [
        ("John Doe", "Sales", 75000, "2022-01-15", "North"),
        ("Jane Smith", "Marketing", 68000, "2021-06-20", "South"),
        ("Mike Johnson", "IT", 85000, "2020-03-10", "East"),
        ("Sarah Williams", "Sales", 72000, "2022-09-05", "West"),
        ("Tom Brown", "HR", 65000, "2021-12-01", "North"),
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO employees VALUES (NULL, ?, ?, ?, ?, ?)',
        employee_data
    )
    
    conn.commit()
    conn.close()

def get_database_schema() -> DatabaseSchema:
    """Get the schema of the current database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    columns = {}
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")
        columns[table] = [row[1] for row in cursor.fetchall()]
    
    conn.close()
    return DatabaseSchema(tables=tables, columns=columns)

def execute_query(sql_query: str) -> Dict[str, Any]:
    """Execute SQL query and return results"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        
        if not rows:
            return {"data": [], "columns": []}
        
        columns = [description[0] for description in cursor.description]
        data = [dict(row) for row in rows]
        
        conn.close()
        return {"data": data, "columns": columns}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query execution error: {str(e)}")

# ==================== LLM FUNCTIONS ====================

def get_system_prompt(schema: DatabaseSchema) -> str:
    """Generate system prompt with database schema"""
    schema_info = "You are an expert SQL query generator and data visualization specialist.\n\n"
    schema_info += "Available Database Schema:\n"
    
    for table, cols in schema.columns.items():
        schema_info += f"\nTable: {table}\nColumns: {', '.join(cols)}\n"
    
    schema_info += """
    
You have two main responsibilities:

1. **SQL Generation**: When given a natural language query, generate accurate SQL queries that retrieve the requested data.
   - Always use valid SQLite syntax
   - Consider date formatting, aggregations, and filtering
   - Return data in a format suitable for visualization

2. **Chart Recommendation**: Based on the query intent and data retrieved, recommend appropriate chart types:
   - Line Chart: Time-series, trends over time
   - Bar Chart: Category comparisons, ranking
   - Pie Chart: Parts of a whole (percentages)
   - Scatter Plot: Correlation between two variables
   - Area Chart: Stacked values over time
   - Table: Detailed data presentation

3. **Insight Generation**: Provide 2-3 key business insights from the data.

IMPORTANT RULES:
- Always generate valid SQL that executes without errors
- If the query is ambiguous, make reasonable assumptions
- Return response in this JSON format ONLY:
{
    "sql_query": "SELECT ...",
    "chart_type": "bar|line|pie|scatter|area|table",
    "title": "Clear chart title",
    "description": "Brief description of what the chart shows",
    "insights": ["Insight 1", "Insight 2", "Insight 3"]
}
"""
    return schema_info

def generate_dashboard_from_query(natural_query: str, conversation_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
    """Use Gemini to convert natural language to SQL and recommend charts"""
    
    schema = get_database_schema()
    system_prompt = get_system_prompt(schema)
    
    # Build conversation context
    messages = [
        {"role": "user", "content": system_prompt},
    ]
    
    if conversation_history:
        messages.extend(conversation_history)
    
    messages.append({"role": "user", "content": natural_query})
    
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(system_prompt + "\n\nUser Query: " + natural_query)
        
        # Parse response
        response_text = response.text
        
        # Extract JSON from response
        try:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_str = response_text[json_start:json_end]
            result = json.loads(json_str)
        except:
            result = {
                "sql_query": "SELECT * FROM sales LIMIT 10;",
                "chart_type": "table",
                "title": "Query Result",
                "description": "Data from your query",
                "insights": ["Unable to parse complex query, showing raw data"]
            }
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

def generate_multiple_charts(natural_query: str) -> List[Dict[str, Any]]:
    """Generate multiple perspectives for complex queries"""
    try:
        model = genai.GenerativeModel('gemini-pro')
        
        schema = get_database_schema()
        
        prompt = f"""
Based on this query: "{natural_query}"

Generate 2-3 different SQL queries that provide complementary perspectives on the same business question.

Return as JSON array:
[
    {{
        "sql_query": "SELECT ...",
        "chart_type": "bar",
        "title": "Chart 1",
        "description": "Description"
    }},
    {{
        "sql_query": "SELECT ...",
        "chart_type": "line",
        "title": "Chart 2",
        "description": "Description"
    }}
]

Database schema:
{json.dumps({table: cols for table, cols in schema.columns.items()})}
"""
        
        response = model.generate_content(prompt)
        response_text = response.text
        
        try:
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            json_str = response_text[json_start:json_end]
            results = json.loads(json_str)
        except:
            results = []
        
        return results
    except Exception as e:
        return []

# ==================== API ENDPOINTS ====================

@app.on_event("startup")
async def startup():
    """Initialize database on startup"""
    if not os.path.exists(DB_PATH):
        init_database()

@app.get("/schema")
async def get_schema():
    """Get current database schema"""
    return get_database_schema()

@app.post("/generate-dashboard", response_model=DashboardResponse)
async def generate_dashboard(query_input: NaturalQuery):
    """Generate dashboard from natural language query"""
    
    try:
        # Generate primary dashboard
        dashboard_config = generate_dashboard_from_query(
            query_input.query,
            query_input.conversation_history
        )
        
        # Execute SQL query
        query_results = execute_query(dashboard_config["sql_query"])
        
        # Generate additional perspectives for complex queries
        additional_charts = generate_multiple_charts(query_input.query)
        
        # Format charts
        charts = [{
            "id": "chart_0",
            "type": dashboard_config.get("chart_type", "bar"),
            "title": dashboard_config.get("title", "Data Visualization"),
            "description": dashboard_config.get("description", ""),
            "data": query_results["data"],
            "columns": query_results["columns"],
            "config": {
                "responsive": True,
                "maintainAspectRatio": True,
            }
        }]
        
        # Add additional charts
        for idx, chart_config in enumerate(additional_charts, 1):
            try:
                chart_results = execute_query(chart_config["sql_query"])
                charts.append({
                    "id": f"chart_{idx}",
                    "type": chart_config.get("chart_type", "bar"),
                    "title": chart_config.get("title", "Data Visualization"),
                    "description": chart_config.get("description", ""),
                    "data": chart_results["data"],
                    "columns": chart_results["columns"],
                    "config": {
                        "responsive": True,
                        "maintainAspectRatio": True,
                    }
                })
            except:
                pass
        
        insights = dashboard_config.get("insights", ["Data loaded successfully"])
        
        return DashboardResponse(
            query=query_input.query,
            charts=charts,
            insights=insights
        )
    
    except Exception as e:
        return DashboardResponse(
            query=query_input.query,
            charts=[],
            insights=[],
            error=str(e)
        )

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """Upload CSV file and create database table"""
    try:
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        
        # Clean table name
        table_name = file.filename.replace('.csv', '').lower().replace(' ', '_')
        
        # Store in database
        conn = sqlite3.connect(DB_PATH)
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        conn.close()
        
        return {
            "message": "CSV uploaded successfully",
            "table_name": table_name,
            "rows": len(df),
            "columns": list(df.columns)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV upload error: {str(e)}")

@app.post("/chat")
async def chat_with_dashboard(query_input: NaturalQuery):
    """Follow-up chat for filtering and modifying dashboards"""
    return await generate_dashboard(query_input)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}