# dune_analytics_mcp_httpx.py
from typing import Optional

from mcp.server.fastmcp import FastMCP
import httpx
import subprocess
import os
import threading
from dotenv import load_dotenv
import pandas as pd
import random

import requests
from bs4 import BeautifulSoup
import structlog
import time
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

# Base URL and API endpoints
BASE_URL = "https://www.footprint.network/api/v1"
DATA_API_URL = "https://vip.footprint.network/api/v1/dataApi/dashcard/data"
CHART_API_URL = "https://vip.footprint.network/api/v1/public/card"

logger = structlog.get_logger(__name__)

# Initialize MCP server
mcp = FastMCP(
    name="Dashboard MCP",
    description="Retrieve raw data from dashboard/chart url",
    dependencies=["httpx", "pandas", "python-dotenv"],
)

GRAPHQL_API = 'https://core-api.dune.com/public/graphql'
EXECUTION_API = 'https://core-api.dune.com/public/execution'

# Direct cookie string from the example
DUNE_COOKIES = 'AMP_MKTG_e76ce253e6=JTdCJTIycmVmZXJyZXIlMjIlM0ElMjJodHRwcyUzQSUyRiUyRnd3dy5nb29nbGUuY29tJTJGJTIyJTJDJTIycmVmZXJyaW5nX2RvbWFpbiUyMiUzQSUyMnd3dy5nb29nbGUuY29tJTIyJTdE; _ga=GA1.1.1640660718.1747030585; cf_clearance=sMwBpEr3lhXc7M9xrNSMmE7kCPHqobnJh.PJezDPafs-1747030587-1.2.1.1-YFKOda.i7A834ldSVk.QLT67tPP_biogN9jeZbQHOzNL_TF7Hsn8yKhzDXsfg1zTJmaSLB1hRbH9AFwpO5IAS_txvciAi8gLPm6WIvjSM82PMjU_uNY95tOIqAKX7ePB3PGZ29eSTx.OJ6sIWh3tLqGfeAhD.J6mZorrSIeB0lZCE2NpTZ20w8Zgdd0is.VM3yQhQIFOFOMWc2BRTNW4nsVvuyoE2eOe_Rp6IcoH9PS6UNCXYdhZGxuW5XwbfhH.NywCNliLdw2cw5WiVLho6NY0uDrDJRrqMsownM3X3ZJYExvbxLdxf7y8.bcJK9_7njeRq62AIkPnyJUrs3JO13ciwuOOqZzBan4evmYxaH0; AMP_e76ce253e6=JTdCJTIyZGV2aWNlSWQlMjIlM0ElMjIzYmQzNjA5Yy05Y2E3LTRjMmItYWY0Mi0wZjRmNDdjMDkzMmYlMjIlMkMlMjJzZXNzaW9uSWQlMjIlM0ExNzQ3MDMwNTg1MzMxJTJDJTIyb3B0T3V0JTIyJTNBZmFsc2UlMkMlMjJsYXN0RXZlbnRUaW1lJTIyJTNBMTc0NzAzMDU5MTE0MCUyQyUyMmxhc3RFdmVudElkJTIyJTNBMyU3RA==; __hstc=178244666.fffa39c8772dae9627b24c2b43611b27.1747030592582.1747030592582.1747030592582.1; hubspotutk=fffa39c8772dae9627b24c2b43611b27; __hssrc=1; __stripe_mid=075ed6b0-13a3-4ffc-a0c3-868fd5ec6ab12938d7; __stripe_sid=55a22581-621f-4658-b6ab-45a29a41771f3af967; _ga_H1G057R0KN=GS2.1.s1747030585$o1$g1$t1747030621$j0$l0$h0; __hssc=178244666.2.1747030592582'

# GraphQL queries
FIND_DASHBOARD_QUERY = """query FindDashboard($filters: DashboardFilterInput!) {
    dashboards(filters: $filters, pagination: {first: 1}) {
        edges {
            node {
                ...FindDashboard
                __typename
            }
            __typename
        }
        __typename
    }
}

fragment User on User {
    id
    name
    profile_image_url: profileImageUrl
    __typename
}

fragment Team on Team {
    id
    name
    handle
    profile_image_url: profileImageUrl
    __typename
}

fragment DashboardVisualization on Visualization {
    id
    type
    name
    description
    options
    created_at: createdAt
    query_details: query {
        query_id: id
        name
        description
        show_watermark: showWatermark
        parameters
        dataset_id: datasetId
        user {
            ...User
            __typename
        }
        team {
            ...Team
            __typename
        }
        __typename
    }
    __typename
}

fragment FindDashboard on Dashboard {
    id
    name
    slug
    isPrivate
    isArchived
    createdAt
    repoLink
    tags
    hasStarred
    isTrending
    mintable
    verificationStatus
    starCount
    pageViewCount(timeframe: TIMEFRAME_ALL)
    user {
        ...User
        __typename
    }
    team {
        ...Team
        __typename
    }
    forkedDashboard {
        slug
        name
        user {
            name
            __typename
        }
        team {
            handle
            __typename
        }
        __typename
    }
    textWidgets {
        id
        text
        options
        __typename
    }
    visualizationWidgets {
        id
        options
        visualization {
            ...DashboardVisualization
            __typename
        }
        __typename
    }
    paramWidgets {
        id
        key
        visualization_widget_id: visualizationWidgetId
        query_id: queryId
        dashboard_id: dashboardId
        options
        __typename
    }
    __typename
}"""

GET_EXECUTION_QUERY = """query GetLatestResultSetIds($canRefresh: Boolean!, $queryId: Int!, $parameters: [ExecutionParameterInput!]) {
    resultSetForQuery(
        canRefresh: $canRefresh
        queryId: $queryId
        parameters: $parameters
    ) {
        completedExecutionId
        failedExecutionId
        pendingExecutionId
        __typename
    }
}"""



class FreeProxyPool:
    def __init__(self):
        self.proxies = set()
        self.working_proxies = set()
        self.lock = threading.Lock()
        self.test_url = "https://httpbin.org/ip"  # 用来测试代理
        self.initialized = False
        self.initialization_thread = None
        self.max_workers = 20  # 最大并行验证代理的线程数

    def fetch_free_proxy_list(self):
        """从free-proxy-list.net获取免费代理"""
        try:
            response = requests.get('https://free-proxy-list.net/', timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', {'id': 'proxylisttable'})

            for row in table.tbody.find_all('tr'):
                cells = row.find_all('td')
                ip = cells[0].text
                port = cells[1].text
                https = cells[6].text

                if https.lower() == 'yes':
                    proxy = f"https://{ip}:{port}"
                else:
                    proxy = f"http://{ip}:{port}"

                with self.lock:
                    self.proxies.add(proxy)

            logger.info(f"[Proxy Pool] Added {len(self.proxies)} proxies from free-proxy-list")
        except Exception as e:
            logger.error(f"[Proxy Pool] Error fetching from free-proxy-list: {e}")

    def fetch_geonode_proxies(self):
        """从Geonode获取免费代理"""
        try:
            url = "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc"
            response = requests.get(url, timeout=10)
            data = response.json()

            for proxy in data.get('data', []):
                ip = proxy.get('ip')
                port = proxy.get('port')
                protocol = proxy.get('protocols')[0].lower() if proxy.get('protocols') else 'http'

                proxy_str = f"{protocol}://{ip}:{port}"
                with self.lock:
                    self.proxies.add(proxy_str)

            logger.info(f"[Proxy Pool] Added proxies from Geonode, total: {len(self.proxies)}")
        except Exception as e:
            logger.error(f"[Proxy Pool] Error fetching from Geonode: {e}")

    def fetch_proxyscrape_proxies(self):
        """从ProxyScrape获取免费代理"""
        try:
            url = "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                proxy_list = response.text.strip().split("\r\n")
                for proxy in proxy_list:
                    if proxy:
                        with self.lock:
                            self.proxies.add(f"http://{proxy}")
                logger.info(f"[Proxy Pool] Added proxies from ProxyScrape, total: {len(self.proxies)}")
        except Exception as e:
            logger.error(f"[Proxy Pool] Error fetching from ProxyScrape: {e}")

    def check_proxy(self, proxy):
        """检查代理是否可用"""
        try:
            proxies = {
                'http': proxy,
                'https': proxy,
            }
            response = requests.get(self.test_url, proxies=proxies, timeout=2)

            if response.status_code == 200:
                with self.lock:
                    self.working_proxies.add(proxy)
                    logger.info(f"[Proxy Pool] Working proxy found: {proxy}")
                return True
        except:
            pass
        return False

    def verify_proxies(self):
        """验证所有代理的可用性"""
        logger.info(f"[Proxy Pool] Verifying {len(self.proxies)} proxies...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            executor.map(self.check_proxy, list(self.proxies))

        logger.info(f"[Proxy Pool] Verification complete. Working proxies: {len(self.working_proxies)}")

    def get_proxy(self):
        """获取一个随机可用代理"""
        with self.lock:
            if not self.working_proxies:
                if self.initialized:
                    # 如果已经初始化过，但没有工作代理，返回None
                    return None
                else:
                    # 如果未初始化，返回None
                    return None
            return random.choice(list(self.working_proxies))

    def refresh(self):
        """刷新代理池"""
        with self.lock:
            self.proxies.clear()
            self.working_proxies.clear()

        # self.fetch_free_proxy_list()
        # self.fetch_geonode_proxies()
        self.fetch_proxyscrape_proxies()

        self.verify_proxies()

        with self.lock:
            self.initialized = True

    def initialize_in_background(self):
        """在后台线程中初始化代理池"""

        def background_init():
            logger.info("[Proxy Pool] Starting background initialization...")
            try:
                self.refresh()
                logger.info(
                    f"[Proxy Pool] Initial proxy pool populated with {len(self.working_proxies)} working proxies")
                # 开始定期维护
                self.maintain_pool()
            except Exception as e:
                logger.error(f"[Proxy Pool] Error during background initialization: {e}")

        # 创建并启动后台线程
        self.initialization_thread = threading.Thread(target=background_init, daemon=True)
        self.initialization_thread.start()

    def maintain_pool(self, interval=1800):
        """定期维护代理池"""
        while True:
            try:
                # 第一次初始化已经完成，这里是后续维护
                time.sleep(interval)  # 先等待，避免过快刷新
                logger.info("[Proxy Pool] Refreshing proxy pool...")
                self.refresh()
                logger.info(
                    f"[Proxy Pool] Proxy pool refreshed. {len(self.working_proxies)} working proxies. Sleeping for {interval} seconds...")
            except Exception as e:
                logger.info(f"[Proxy Pool] Error during proxy pool maintenance: {e}")
                time.sleep(300)  # 出错后等待5分钟再尝试


# # 初始化代理池
# proxy_pool = FreeProxyPool()

# # 异步启动代理池初始化
# logger.info("[Proxy Pool] Starting proxy pool in background...")
# proxy_pool.initialize_in_background()

def run_curl_command(url, data, is_json=True, use_proxy=False):
    """
    Run a curl command to make an HTTP request.

    Args:
        url: The URL to send the request to
        data: The data to send (either JSON or raw data)
        is_json: Whether the data is JSON (if True, adds Content-Type header)
        use_proxy: Whether to use a proxy (if False, uses direct connection)

    Returns:
        dict: Response data parsed as JSON or None if failed
    """
    max_retries = 2

    for retry in range(max_retries):
        try:
            # 创建基本curl命令
            cmd = [
                'curl', url,
                '-H', 'accept: */*',
                '-H', 'accept-language: zh-CN,zh;q=0.9',
                '-b', DUNE_COOKIES,
                '-H', 'origin: https://dune.com',
                '-H', 'priority: u=1, i',
                '-H', 'referer: https://dune.com/',
                '-H', 'sec-ch-ua: "Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
                '-H', 'sec-ch-ua-mobile: ?0',
                '-H', 'sec-ch-ua-platform: "macOS"',
                '-H', 'sec-fetch-dest: empty',
                '-H', 'sec-fetch-mode: cors',
                '-H', 'sec-fetch-site: same-site',
                '-H',
                'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            ]

            # 如果使用代理，添加代理参数
            if use_proxy and os.getenv('IP_PROXY') and os.getenv('IP_PROXY_USER'):
                cmd.extend(['--proxy', os.getenv("IP_PROXY"), '--proxy-user', os.getenv('IP_PROXY_USER')])
                # proxy = proxy_pool.get_proxy()
                # if proxy:
                #     # 提取代理地址和端口
                #     if proxy.startswith('http://'):
                #         proxy_parts = proxy[7:].split(':')
                #     elif proxy.startswith('https://'):
                #         proxy_parts = proxy[8:].split(':')
                #     else:
                #         # 跳过此次重试，获取新代理
                #         logger.info(f"Invalid proxy format: {proxy}, retrying... ({retry+1}/{max_retries})")
                #         continue
                #
                #     if len(proxy_parts) != 2:
                #         logger.info(f"Invalid proxy format: {proxy}, retrying... ({retry+1}/{max_retries})")
                #         continue

                # proxy_host = proxy_parts[0]
                # proxy_port = proxy_parts[1]
                # cmd.extend(['-x', f"{proxy_host}:{proxy_port}"])
                # logger.info(f"Using proxy: {proxy_host}:{proxy_port}")
                # else:
                #     # 如果代理池未初始化完成或没有可用代理，直接使用无代理连接
                #     logger.info(f"No proxy available, trying direct connection... ({retry+1}/{max_retries})")
                #     use_proxy = False

            # 添加Content-Type
            if is_json:
                cmd.extend(['-H', 'content-type: application/json'])

            # 添加数据
            if isinstance(data, dict) or isinstance(data, list):
                data_str = json.dumps(data)
                cmd.extend(['--data-raw', data_str])
            else:
                cmd.extend(['--data-raw', str(data)])

            # 输出更简洁的命令日志
            logger.info(f"Running curl to {url} (retry {retry + 1}/{max_retries})")

            # 执行curl
            result = subprocess.run(cmd, capture_output=True, text=True)


            if result.returncode != 0:
                logger.info(f"Curl command failed with return code {result.returncode}: {result.stderr}")
                if use_proxy:
                    logger.info("Retrying with a different proxy...")
                continue

            try:
                json_response = json.loads(result.stdout)
                logger.info("Curl Result", result=json_response)
                return json_response
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON response: {result.stdout[:100]}...")
                if "Cloudflare" in result.stdout or "cloudflare" in result.stdout.lower():
                    logger.error("Cloudflare detected, trying with a different proxy...")
                continue

        except Exception as e:
            logger.error(f"Error during curl execution (retry {retry + 1}/{max_retries}): {e}")

    # 如果所有重试都失败了，尝试直接连接（如果之前使用了代理）
    if use_proxy:
        logger.infot("All proxy attempts failed, trying direct connection...")
        return run_curl_command(url, data, is_json, use_proxy=False)

    logger.info("All retries failed")
    return None


def parse_dune_url(url):
    """
    Parse a Dune dashboard URL to extract handle and slug.

    Args:
        url: The Dune dashboard URL

    Returns:
        tuple: (handle, slug) or (None, None) if invalid
    """
    parsed_url = urlparse(url)
    if 'dune.com' not in parsed_url.netloc:
        return None, None

    path_parts = parsed_url.path.strip('/').split('/')
    if len(path_parts) != 2:
        return None, None

    return path_parts[0], path_parts[1]


def fetch_dashboard_info(handle, slug):
    """
    Fetch dashboard information from Dune API.

    Args:
        handle: The user/team handle
        slug: The dashboard slug

    Returns:
        dict: Dashboard data or None if failed
    """
    dashboard_query = {
        "operationName": "FindDashboard",
        "variables": {
            "filters": {
                "slug": {"equals": slug},
                "handle": {"equals": handle}
            }
        },
        "query": FIND_DASHBOARD_QUERY
    }

    response = run_curl_command(GRAPHQL_API, dashboard_query)


    if not response:
        return None

    # Check if dashboard exists
    if not response.get('data', {}).get('dashboards', {}).get('edges'):
        return None

    return response['data']['dashboards']['edges'][0]['node']


def get_execution_id(query_id, parameters):
    """
    Get execution ID for a query.

    Args:
        query_id: The query ID
        parameters: Query parameters

    Returns:
        str: Execution ID or None if failed
    """
    execution_query = {
        "operationName": "GetLatestResultSetIds",
        "variables": {
            "queryId": int(query_id),
            "parameters": parameters,
            "canRefresh": True
        },
        "query": GET_EXECUTION_QUERY
    }

    response = run_curl_command(GRAPHQL_API, execution_query)

    if not response:
        return None

    return response.get('data', {}).get('resultSetForQuery', {}).get('completedExecutionId')


def fetch_chart_data(execution_id, query_id, parameters, columns: Optional[list] = None):
    """
    Fetch chart data using execution ID.

    Args:
        execution_id: The execution ID
        query_id: The query ID
        parameters: Query parameters
        columns: Output columns to fetch

    Returns:
        dict: Chart data or None if failed
    """
    chart_data_query = {
        "execution_id": execution_id,
        "query_id": int(query_id),
        "parameters": parameters,
        "sampling": {"count": 8000}
    }
    if columns:
        chart_data_query['output_columns'] = columns

    response = run_curl_command(EXECUTION_API, chart_data_query)

    return response


def process_visualization(visualization):
    """
    Process a visualization to extract query details and options.

    Args:
        visualization: The visualization data

    Returns:
        tuple: (query_id, parameters, options, columns, viz_info) or None if invalid
    """
    if not visualization:
        return None

    query_details = visualization.get('query_details', {})
    if not query_details:
        return None

    query_id = query_details.get('query_id')
    parameters = query_details.get('parameters', [])
    name = query_details.get('name', [])

    if not query_id:
        return None

    # Extract visualization info
    viz_info = {
        "visualization_id": visualization.get('id'),
        "visualization_type": visualization.get('type'),
        "visualization_name": visualization.get('name')
    }

    # Process options
    options = visualization.get('options', {})
    if isinstance(options, str):
        try:
            options = json.loads(options)
        except:
            options = {}

    # Extract columns from options
    columns = []
    column_mapping = options.get('columnMapping', {})
    if column_mapping:
        columns = list(column_mapping.keys())

    return query_id, name, parameters, options, columns, viz_info

def get_dune_chart_data(url: str) -> str:
    parsed_url = urlparse(url)
    query_id = parsed_url.path.split('/')[2]
    parameters = []
    logger.info(f"Getting execution ID for query {query_id}...")
    execution_id = get_execution_id(query_id, parameters)
    if not execution_id:
        return json.dumps({"error": "No execution found"})

    # Step 5: Fetch chart data
    logger.info(f"Fetching chart data for execution {execution_id}...")
    chart_data = fetch_chart_data(execution_id, query_id, parameters)
    if not chart_data:
        return json.dumps({"error": "No chart data found"})
    return json.dumps(chart_data)




def get_dune_dashboard_data(url: str) -> str:
    """
    Retrieve chart data from a Dune dashboard URL.

    Args:
        url: The URL of the Dune dashboard, e.g., https://dune.com/cryptokoryo/crypto-buy-signal

    Returns:
        JSON string containing the chart data
    """
    try:
        # Step 1: Parse URL to get handle and slug
        handle, slug = parse_dune_url(url)
        if not handle or not slug:
            return json.dumps({"error": "Invalid Dune dashboard URL format"})

        # Step 2: Fetch dashboard info
        logger.info(f"Fetching dashboard info for {handle}/{slug}...")
        dashboard_node = fetch_dashboard_info(handle, slug)
        if not dashboard_node:
            return json.dumps({"error": "Dashboard not found or access denied by Cloudflare."})

        # Get visualization widgets
        visualization_widgets = dashboard_node.get('visualizationWidgets', [])
        if not visualization_widgets:
            return json.dumps({"error": "No visualizations found in dashboard"})

        # Step 3: Process each visualization widget
        charts_data = []

        for widget in visualization_widgets:
            visualization = widget.get('visualization', {})
            processed_data = process_visualization(visualization)

            if not processed_data:
                continue

            query_id, name,parameters, options, columns, viz_info = processed_data

            # Step 4: Get execution ID for the query
            logger.info(f"Getting execution ID for query {query_id}...")
            execution_id = get_execution_id(query_id, parameters)
            if not execution_id:
                continue

            # Step 5: Fetch chart data
            logger.info(f"Fetching chart data for execution {execution_id}...")
            chart_data = fetch_chart_data(execution_id, query_id, parameters, columns)
            if not chart_data:
                continue

            # Step 6: Extract and format chart result
            chart_result = {
                **viz_info,
                "query_id": query_id,
                "options": options
            }

            if chart_data.get('execution_succeeded'):
                succeeded_data = chart_data['execution_succeeded']
                chart_result['columns'] = succeeded_data.get('columns', [])
                chart_result['columns_metadata'] = succeeded_data.get('columns_metadata', [])
                chart_result['data'] = succeeded_data.get('data', [])
                chart_result['total_row_count'] = succeeded_data.get('total_row_count', 0)

            charts_data.append(chart_result)

        # Step 7: Return dashboard data with all charts
        result = {
            "dashboard_name": dashboard_node.get('name'),
            "dashboard_slug": dashboard_node.get('slug'),
            "dashboard_id": dashboard_node.get('id'),
            "user": dashboard_node.get('user', {}).get('name'),
            "charts": charts_data
        }

        return json.dumps(result)

    except Exception as e:
        return json.dumps({"error": f"Failed to process dashboard: {str(e)}"})

# @mcp.tool()
def get_footprint_chart_data(chart_url: str) -> str:
    """Get raw data from a Footprint Network chart and return as JSON string
    
    Args:
        chart_url: URL of the Footprint Network chart (e.g., https://www.footprint.network/@Higi/Sui-Bridge?type=chart)

    Returns:
        JSON string containing all chart data from the chart
    """
    try:
        # Parse chart URL to extract username, dashboard name, and chart name
        parts = chart_url.split("?")[0].split("/")
        chart_uuid = parts[-1].split("fp-")[-1]

        url=f"{CHART_API_URL}/{chart_uuid}/query"

        parameters = {}
        if "?" in chart_url:
            params_str = chart_url.split("?")[1].split("#")[0]
            for param in params_str.split("&"):
                if "=" in param:
                    key, value = param.split("=")
                    parameters[key] = value
        
        if parameters:
            url = url + "?" + "&".join([f"{k}={v}" for k, v in parameters.items()])

        with httpx.Client() as client:
            response = client.get(url, timeout=60)
            response.raise_for_status()
            data = response.json()

            # Extract columns and rows from response
            columns = [item.get("display_name") for item in data.get("data", {}).get("cols", [])]
            rows = data.get("data", {}).get("rows", [])
            
            # 使用 pandas 将数据转换为键值对数组
            df = pd.DataFrame(rows, columns=columns)
            result = json.loads(df.to_json(orient='records'))

            return json.dumps({"data": result})

    except httpx.HTTPError as e:
        return f"Error: HTTP error fetching chart data: {str(e)}"
    except Exception as e:
        return f"Error: Failed to get chart data: {str(e)}"
        

    

# @mcp.tool()
def get_footprint_dashboard_data(dashboard_url: str) -> str:
    """Get raw data from a Footprint Network dashboard and return as JSON string
    
    Args:
        dashboard_url: URL of the Footprint Network dashboard (e.g., https://www.footprint.network/@Higi/Sui-Bridge)

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
            for param in params_str.split("&"):
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


@mcp.tool()
def get_data(url: str) -> str:
    """Get raw data from a graph (eg: dashboard, chart) and return as JSON string

       Args:
           url: URL of the graph (e.g., https://www.footprint.network/guest/chart/Total-Pet-Minted-fp-e9135cea-f9cd-4c59-8371-b3078c9b1bbe)

       Returns:
           JSON string containing all chart data from the graph
       """
    if "footprint.network" in url:
        if "/chart" in url:
            return get_footprint_chart_data(url)
        else:
            return get_footprint_dashboard_data(url)
    if "dune.com" in url:
        if "queries" in url:
            return get_dune_chart_data(url)
        else:
            return get_dune_dashboard_data(url)
    return "Error: This Url Not supported"

# Run the server
if __name__ == "__main__":
    mcp.run()