# Arquitectura de CaféDMC

Stack: ver [ADR-0001](adr/0001-stack.md).

## 1. Contexto (C4 nivel 1)

```mermaid
flowchart LR
    cliente["Cliente<br/>(persona)"]
    dev["Desarrollador<br/>(persona)"]
    agente["Agente IA"]
    sistema["CaféDMC<br/>(sistema de pedidos)"]

    cliente -->|"Ve menú y hace pedidos"| sistema
    dev -->|"Desarrolla y prueba"| sistema
    dev -->|"Da instrucciones"| agente
    agente -->|"Lee, prueba y modifica"| sistema
```

## 2. Contenedores (C4 nivel 2)

```mermaid
flowchart LR
    cliente["Cliente"]
    agente["Agente IA"]

    subgraph cafedmc["CaféDMC"]
        ui["Pantalla<br/>(Streamlit)"]
        subgraph api["API (FastAPI)"]
            catalogo["Catálogo"]
            pedidos["Pedidos"]
        end
        db[("SQLite")]
    end

    mcp["Servidores MCP"]

    cliente -->|"Usa"| ui
    ui -->|"HTTP/JSON"| catalogo
    ui -->|"HTTP/JSON"| pedidos
    catalogo -->|"SQL"| db
    pedidos -->|"SQL"| db
    agente -->|"Consulta"| mcp
    mcp -.->|"Solo lectura"| db
    agente -->|"Escrituras HTTP"| api
```

El agente lee la base solo a través de MCP; todo cambio de datos pasa por la API.
