#!/usr/bin/env python3
"""
Test script to demonstrate proper Claude Flow queen coordination
"""

import subprocess
import json
import time

def test_claude_flow_coordination():
    """Test Claude Flow with proper queen coordination setup"""
    
    print("🐝 Testing Claude Flow Queen Coordination")
    print("=" * 50)
    
    # Step 1: Initialize hierarchical swarm
    print("\n1. Initializing Hierarchical Swarm...")
    try:
        result = subprocess.run([
            "npx", "claude-flow@alpha", "swarm", "init", 
            "--topology", "hierarchical",
            "--max-agents", "5"
        ], capture_output=True, text=True)
        print(f"   ✓ Swarm initialized: {result.stdout}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Step 2: Create a test task
    print("\n2. Creating Test Task...")
    try:
        result = subprocess.run([
            "npx", "claude-flow@alpha", "swarm", "task",
            "Analyze Django project structure and create documentation"
        ], capture_output=True, text=True)
        print(f"   ✓ Task created: {result.stdout}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Step 3: Check swarm status
    print("\n3. Checking Swarm Status...")
    try:
        result = subprocess.run([
            "npx", "claude-flow@alpha", "swarm", "status", "--json"
        ], capture_output=True, text=True)
        if result.stdout:
            status = json.loads(result.stdout)
            print(f"   ✓ Active Agents: {status.get('agentCount', 0)}")
            print(f"   ✓ Tasks: {status.get('taskCount', 0)}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n" + "=" * 50)
    print("📝 Proper Queen Coordination Setup:")
    print("""
    1. The Queen Coordinator should automatically:
       - Break down complex tasks into subtasks
       - Assign subtasks to worker agents
       - Monitor progress and provide feedback
       - Coordinate results from all agents
    
    2. If the queen isn't sending instructions, check:
       - Claude Flow is properly installed: npx claude-flow@alpha --version
       - MCP server is running: Check Claude Code settings
       - Swarm is initialized with hierarchical topology
       - Queen agent is spawned as type 'coordinator'
    
    3. To fix queen coordination issues:
       - Restart Claude Code to refresh MCP connection
       - Ensure .claude/settings.json has claude-flow MCP configured
       - Use 'hierarchical' topology for queen-based coordination
       - Always spawn a 'coordinator' type agent as the queen
    """)

if __name__ == "__main__":
    test_claude_flow_coordination()