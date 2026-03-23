import os
import requests
from fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

RABBITMQ_API_URL = os.getenv("RABBITMQ_API_URL", "http://localhost:15672/api")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

# Initialize FastMCP server
mcp = FastMCP("RabbitMQ Expert Server")

def _request(endpoint):
    """Internal helper to make RabbitMQ API requests."""
    try:
        response = requests.get(
            f"{RABBITMQ_API_URL}/{endpoint}",
            auth=(RABBITMQ_USER, RABBITMQ_PASS),
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

@mcp.tool()
def get_overview() -> str:
    """Provides a general overview of the RabbitMQ cluster status, health, and alarms."""
    overview = _request("overview")
    if "error" in overview:
        return f"Error fetching overview: {overview['error']}"
    
    # Extract relevant info
    cluster_name = overview.get("cluster_name", "Unknown")
    listeners = overview.get("listeners", [])
    object_totals = overview.get("object_totals", {})
    message_stats = overview.get("message_stats", {})
    
    # Check for node alarms
    nodes = _request("nodes")
    alarms = []
    if not isinstance(nodes, dict): # nodes returns a list
        for node in nodes:
            if node.get("mem_alarm", False):
                alarms.append(f"Memory alarm on {node.get('name')}")
            if node.get("disk_free_alarm", False):
                alarms.append(f"Disk free alarm on {node.get('name')}")

    res = f"Cluster: {cluster_name}\n"
    res += f"Total Queues: {object_totals.get('queues', 0)}\n"
    res += f"Total Connections: {object_totals.get('connections', 0)}\n"
    res += f"Total Consumers: {object_totals.get('consumers', 0)}\n"
    res += f"Messages Ready: {overview.get('queue_totals', {}).get('messages_ready', 0)}\n"
    
    if alarms:
        res += "\nALERTS:\n" + "\n".join(alarms)
    else:
        res += "\nNo active memory or disk alarms."
        
    return res

@mcp.tool()
def list_queues() -> str:
    """Lists all queues with their status, message counts, and consumer counts."""
    queues = _request("queues")
    if "error" in queues:
        return f"Error fetching queues: {queues['error']}"
    
    if not queues:
        return "No queues found."
    
    res = "Queues List:\n"
    for q in queues:
        res += f"- {q.get('name')}: {q.get('messages', 0)} msgs (Ready: {q.get('messages_ready', 0)}, Unacked: {q.get('messages_unacknowledged', 0)}), Consumers: {q.get('consumers', 0)}, State: {q.get('state')}\n"
    return res

@mcp.tool()
def list_users() -> str:
    """Lists all RabbitMQ users and their tags (permissions)."""
    users = _request("users")
    if "error" in users:
        return f"Error fetching users: {users['error']}"
    
    res = "Users List:\n"
    for u in users:
        res += f"- {u.get('name')} (Tags: {u.get('tags')})\n"
    return res

@mcp.tool()
def find_issues() -> str:
    """Analyzes nodes and queues for common issues like high unacked messages, memory alarms, or no consumers."""
    queues = _request("queues")
    nodes = _request("nodes")
    
    issues = []
    
    # Check Queues
    if not isinstance(queues, dict):
        for q in queues:
            if q.get("messages_unacknowledged", 0) > 1000:
                issues.append(f"Queue '{q.get('name')}' has high unacknowledged messages: {q.get('messages_unacknowledged')}")
            if q.get("consumers", 0) == 0 and q.get("messages", 0) > 0:
                issues.append(f"Queue '{q.get('name')}' has messages but no consumers.")
    
    # Check Nodes
    if not isinstance(nodes, dict):
        for node in nodes:
            if node.get("mem_alarm", False):
                issues.append(f"NODE ALERT: Memory alarm on {node.get('name')}")
            if node.get("disk_free_alarm", False):
                issues.append(f"NODE ALERT: Disk free alarm on {node.get('name')}")

    if not issues:
        return "No significant issues detected in the cluster."
    
    return "Potential Issues Found:\n" + "\n".join(f"- {i}" for i in issues)

@mcp.tool()
def get_best_practices(topic: str = "general") -> str:
    """Provides best practices for RabbitMQ based on the requested topic (e.g., 'queues', 'scaling', 'exchanges', 'general', 'consumers')."""
    topics = {
        "general": """
- Keep your queues short.
- Use persistent messages for durability.
- Use Lazy Queues for large message backlogs.
- Monitor your cluster resources (RAM, Disk).
- Use a connection pool to avoid opening/closing connections frequently.
        """,
        "queues": """
- Avoid very long queues (use TTL or max-length if possible).
- Use Quorum Queues for high availability.
- Don't use too many priorities (keep it below 10).
- Monitor queue length and unacknowledged messages.
        """,
        "scaling": """
- Scale consumers horizontally for faster processing.
- Use Consistent Hashing exchanges for scaling consumers across queues.
- Use Sharding plugin for very high throughput.
- Separate Management UI from production traffic.
- Cluster across multiple nodes/zones for reliability.
        """,
        "exchanges": """
- Prefer 'topic' or 'direct' exchanges over 'fanout' if you need routing logic.
- Use Dead Letter Exchanges (DLX) for failed messages.
- Avoid excessive binding creation (it's expensive).
        """,
        "consumers": """
- Use Manual Acknowledgements for reliability.
- Set a proper Prefetch count (QoS) to avoid overwhelming consumers.
- Handle consumer cancellations and connection drops gracefully.
- Use multiple threads/processes per consumer if the workload is CPU-bound.
        """
    }
    
    return topics.get(topic.lower(), "Topic not found. Try: general, queues, scaling, exchanges, consumers.")

@mcp.tool()
def get_config_guide(aspect: str = "performance") -> str:
    """Provides configuration snippets and advice for various RabbitMQ aspects (e.g., 'performance', 'security', 'clustering')."""
    guides = {
        "performance": """
Set in rabbitmq.conf:
- vm_memory_high_watermark.relative = 0.4 (Adjust based on RAM)
- disk_free_limit.absolute = 2GB
- collect_statistics_interval = 5000 (Reduce if management UI is slow)
        """,
        "security": """
Best practices:
- Delete the default 'guest' user or restrict it to localhost.
- Use TLS/SSL for all client connections (port 5671).
- Use Virtual Hosts (vhosts) to isolate environments.
- Implement fine-grained permissions (regexp for read/write/configure).
        """,
        "clustering": """
Configuring a cluster:
- All nodes must share the same Erlang Cookie.
- Use 'rabbitmqctl join_cluster' to add nodes.
- Use a Load Balancer (like HAProxy) in front of nodes.
- Prefer an odd number of nodes (3, 5) for Quorum Queues.
        """
    }
    return guides.get(aspect.lower(), "Guide not found. Try: performance, security, clustering.")

if __name__ == "__main__":
    mcp.run()
