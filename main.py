# dune_analytics_mcp_httpx.py
from mcp.server.fastmcp import FastMCP
import httpx
import os
from dotenv import load_dotenv
import pandas as pd
import time
import json
import asyncio

# Load environment variables
load_dotenv()

# Base URL and API endpoints
BASE_URL = "https://www.footprint.network/api/v1"
DATA_API_URL = "https://vip.footprint.network/api/v1/dataApi/dashcard/data"

# Initialize MCP server
mcp = FastMCP(
    name="Footprint Network Dashboard MCP",
    description="Retrieve raw data from Footprint Network dashboards",
    dependencies=["httpx", "pandas", "python-dotenv"],
)

@mcp.tool()
def get_dashboard_data(dashboard_url: str) -> str:
    """Get raw data from a Footprint Network dashboard and return as JSON string
    
    Args:
        dashboard_url: URL of the Footprint Network dashboard (e.g., https://www.footprint.network/@Higi/Sui-Bridge)
        api_token: Your Footprint Network API token (optional if set in environment variables)
    
    Returns:
        JSON string containing all chart data from the dashboard
    """
    try:
        # Parse dashboard URL to extract username and dashboard name
        ## drop the #type=dashboard
        dashboard_url = dashboard_url.split("#type")[0]
        parts = dashboard_url.split("@")[1].split("?")[0].split("/")
        username = parts[0]
        dashboard_name = parts[1]
        
        # Extract parameters if any
        parameters = {}
        if "?" in dashboard_url:
            params_str = dashboard_url.split("?")[1].split("#")[0]
            for param in params_str.split("~"):
                if "=" in param:
                    key, value = param.split("=")
                    parameters[key] = value
        

        
        # Get dashboard UUID
        uuid = get_dashboard_uuid(username, dashboard_name)
        if uuid.startswith("Error:"):
            return uuid
        
        # Get chart data
        charts_data = get_charts_data(uuid, parameters)

        # Return as JSON string
        return json.dumps({"charts": charts_data})
    except Exception as e:
        return f"Error processing dashboard data: {str(e)}"

def get_dashboard_uuid(username, dashboard_name):
    """Get dashboard UUID from Footprint Network API"""
    url = f"{BASE_URL}/dashboard/basic"
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "client_request_time": str(int(time.time() * 1000)),
        "content-type": "application/json",
        "origin": "https://www.footprint.network",
        "referer": f"https://www.footprint.network/@{username}/{dashboard_name}",
        "user-agent": "MCP-Footprint-Client"
    }
    
    payload = {
        "dashboardName": dashboard_name,
        "userName": username
    }
    print(payload)

    try:
        with httpx.Client() as client:
            response = client.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            print("data", data)
            return data["data"]["uuid"]
    except httpx.HTTPError as e:
        return f"Error: HTTP error fetching dashboard UUID: {str(e)}"
    except Exception as e:
        return f"Error: Failed to get dashboard UUID: {str(e)}"

def get_charts_data(dashboard_uuid, parameters=None):
    """Get chart data from Footprint Network API using dashboard UUID"""
    headers = {
        "X-Fastest-App": "richer",
        "Content-Type": "application/json"
    }
    
    payload = {
        "publicUuid": dashboard_uuid,
        "dashboardId": "",
        "paramters": parameters or {}
    }
    
    try:
        with httpx.Client() as client:
            response = client.post(DATA_API_URL, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
    except httpx.HTTPError as e:
        return f"Error: HTTP error fetching chart data: {str(e)}"
    except Exception as e:
        return f"Error: Failed to get chart data: {str(e)}"

# Run the server
if __name__ == "__main__":
    # result = get_dashboard_data(dashboard_url="https://www.footprint.network/@Traevon/Pixels-Mockup#type=dashboard")
    # print(result)
    mcp.run(transport="sse")
