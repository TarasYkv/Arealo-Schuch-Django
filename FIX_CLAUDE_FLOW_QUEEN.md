# 🐝 Claude Flow Queen Coordination Fix Guide

## Problem
Die Queen sendet keine Anweisungen bei Claude Flow Tasks.

## Ursache
Claude Flow kann die benötigten Module nicht finden und fällt auf einen eingebauten Executor zurück, der die Queen-Koordination nicht richtig implementiert.

## Lösung

### 1. Claude Code Neustart mit korrekter MCP Konfiguration

Stelle sicher, dass Claude Flow als MCP Server in Claude Code konfiguriert ist:

```bash
# Füge Claude Flow MCP Server hinzu (stdio mode - empfohlen)
claude mcp add claude-flow npx claude-flow@alpha mcp start
```

### 2. Korrekte Verwendung der Claude Flow Swarm Tools

Die Queen-Koordination funktioniert nur, wenn du die MCP Tools korrekt verwendest:

```python
# SCHRITT 1: Initialisiere hierarchischen Swarm
mcp__claude-flow__swarm_init {
    topology: "hierarchical",  # WICHTIG: Nur hierarchical hat eine Queen!
    maxAgents: 8,
    strategy: "adaptive"
}

# SCHRITT 2: Spawne Queen Coordinator (MUSS zuerst kommen!)
mcp__claude-flow__agent_spawn {
    type: "coordinator",      # WICHTIG: Coordinator = Queen
    name: "Queen Coordinator",
    capabilities: ["leadership", "task-distribution", "decision-making"]
}

# SCHRITT 3: Spawne Worker Agents
mcp__claude-flow__agent_spawn { type: "analyst", name: "Analyst 1" }
mcp__claude-flow__agent_spawn { type: "coder", name: "Coder 1" }
mcp__claude-flow__agent_spawn { type: "tester", name: "Tester 1" }

# SCHRITT 4: Orchestriere Task (Queen verteilt automatisch)
mcp__claude-flow__task_orchestrate {
    task: "Deine Aufgabe hier",
    strategy: "adaptive",
    priority: "high"
}
```

### 3. Alternative: Direkte Task-Tool Verwendung

Wenn die MCP Tools nicht funktionieren, verwende das Task Tool direkt mit koordinierenden Anweisungen:

```python
# Spawne koordinierende Agents mit dem Task Tool
Task(
    description="Queen Coordinator",
    prompt="""Du bist die Queen eines hierarchischen Swarms. 
    Deine Aufgabe:
    1. Analysiere die Hauptaufgabe
    2. Teile sie in Unteraufgaben auf
    3. Weise jedem Worker-Agent eine spezifische Aufgabe zu
    4. Koordiniere die Ergebnisse
    
    Hauptaufgabe: [DEINE AUFGABE]
    
    Erstelle einen detaillierten Plan und Anweisungen für jeden Agent.""",
    subagent_type="coordinator"
)
```

### 4. Debugging Befehle

```bash
# Prüfe Claude Flow Version
npx claude-flow@alpha --version

# Prüfe MCP Server Status
claude mcp list

# Teste Swarm direkt
npx claude-flow@alpha swarm test

# Verbose Logging
export DEBUG=claude-flow:*
npx claude-flow@alpha swarm status --verbose
```

### 5. Häufige Fehler und Lösungen

| Problem | Lösung |
|---------|---------|
| "Compiled swarm module not found" | Neuinstallation: `npm install -g claude-flow@alpha` |
| "Failed to spawn Claude Code" | Claude Code neustarten und MCP Server prüfen |
| Queen sendet keine Anweisungen | Hierarchical topology verwenden + Coordinator agent zuerst spawnen |
| Agents arbeiten nicht zusammen | Memory coordination aktivieren mit `mcp__claude-flow__memory_usage` |

### 6. Funktionierendes Beispiel

```bash
# Komplette funktionierende Sequenz:
1. mcp__claude-flow__swarm_init { topology: "hierarchical" }
2. mcp__claude-flow__agent_spawn { type: "coordinator", name: "Queen" }
3. mcp__claude-flow__agent_spawn { type: "analyst" }
4. mcp__claude-flow__agent_spawn { type: "coder" }
5. mcp__claude-flow__memory_usage { action: "store", key: "task", value: "..." }
6. mcp__claude-flow__task_orchestrate { task: "Build feature X" }
7. mcp__claude-flow__swarm_monitor { duration: 10 }
```

## Sofortmaßnahmen

1. **Claude Code neustarten**
2. **MCP Server überprüfen**: `claude mcp list`
3. **Hierarchical Swarm mit Queen initialisieren** (siehe oben)
4. **Task Tool als Fallback verwenden** wenn MCP nicht funktioniert

## Kontakt für weitere Hilfe

- GitHub Issues: https://github.com/ruvnet/claude-flow/issues
- Documentation: https://github.com/ruvnet/claude-flow/docs