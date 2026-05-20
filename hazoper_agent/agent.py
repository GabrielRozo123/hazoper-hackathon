import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.adk.agents.llm_agent import Agent
from psm_metrics import PSMScoringEngine, ComplianceProfile, PROFILE_BR_CETESB, PROFILE_US_OSHA
from mapa_aloha import gerar_mapa_aloha, CENARIOS


# ---------------------------------------------------------
# TOOLS — PSM Agent
# ---------------------------------------------------------

def buscar_dados_planta(nome_planta: str = "ABL Cosmópolis") -> dict:
    """
    Busca os dados PSM de uma planta industrial no banco de dados.
    Retorna os KPIs necessários para calcular a maturidade PSM.
    nome_planta: nome da planta a ser auditada
    """
    plantas = {
        "ABL Cosmópolis": {
            "nome": "ABL Cosmópolis",
            "endereco": "Rod. SP-332, Km 135, Cosmópolis-SP",
            "setor": "Farmacêutico",
            "valid_hazop_nodes": 85,
            "total_risk_nodes": 100,
            "maintenance_done": 75,
            "total_ecs_inventory": 100,
            "mocs_qa_approved": 91,
            "total_mocs_open": 100,
            "active_physical_locks": 17,
            "total_hazardous_energies": 100,
            "jurisdiction": "BR",
            "fonte": "RISP v1 — ESUPERCORP/Hazoper 2026"
        }
    }

    planta = plantas.get(nome_planta)
    if not planta:
        return {
            "status": "erro",
            "mensagem": f"Planta '{nome_planta}' não encontrada.",
            "plantas_disponíveis": list(plantas.keys())
        }

    return {"status": "sucesso", "dados": planta}


def calcular_maturidade_psm(
    valid_hazop_nodes: int,
    total_risk_nodes: int,
    maintenance_done: int,
    total_ecs_inventory: int,
    mocs_qa_approved: int,
    total_mocs_open: int,
    active_physical_locks: int,
    total_hazardous_energies: int,
    jurisdiction: str = "BR"
) -> dict:
    """
    Calcula maturidade PSM via Kernel H3X.
    jurisdiction: 'BR' para CETESB, 'US' para OSHA
    """
    profile_data = PROFILE_US_OSHA if jurisdiction == "US" else PROFILE_BR_CETESB
    profile = ComplianceProfile(profile_data)
    engine = PSMScoringEngine(profile=profile)
    return engine.run_full_audit(
        valid_hazop_nodes=valid_hazop_nodes,
        total_risk_nodes=total_risk_nodes,
        maintenance_done=maintenance_done,
        total_ecs_inventory=total_ecs_inventory,
        mocs_qa_approved=mocs_qa_approved,
        total_mocs_open=total_mocs_open,
        active_physical_locks=active_physical_locks,
        total_hazardous_energies=total_hazardous_energies
    )


# ---------------------------------------------------------
# TOOLS — ALOHA Agent
# ---------------------------------------------------------

def listar_cenarios_aloha() -> dict:
    """Lista todos os cenários ALOHA disponíveis."""
    return {
        "total": len(CENARIOS),
        "cenarios": CENARIOS,
        "planta": "ABL Cosmópolis — Rod. SP-332, Km 135"
    }


def gerar_mapa_zona_ameaca(cenario_id: str, direcao_vento: float = 90) -> dict:
    """
    Gera mapa interativo de zonas de ameaça ALOHA.
    cenario_id: 'S-01' até 'S-08'
    direcao_vento: 0=Norte, 90=Leste, 180=Sul, 270=Oeste
    """
    try:
        caminho = gerar_mapa_aloha(cenario_id, direcao_vento)
        return {
            "status": "sucesso",
            "cenario_id": cenario_id,
            "mapa_path": caminho,
            "mensagem": f"Mapa gerado: {caminho}"
        }
    except ValueError as e:
        return {"status": "erro", "mensagem": str(e)}


def analisar_pior_cenario() -> dict:
    """Identifica e retorna o cenário ALOHA mais crítico disponível."""
    pior = max(CENARIOS, key=lambda c: c.get("zona_r") or 0)
    return {
        "pior_cenario": pior,
        "motivo": "Maior zona vermelha de perigo imediato"
    }


# ---------------------------------------------------------
# SUB-AGENTE 1 — PSM Specialist
# ---------------------------------------------------------

psm_agent = Agent(
    model='gemini-2.5-flash',
    name='psm_specialist',
    description='Especialista em cálculo de maturidade PSM industrial. Busca dados da planta automaticamente e usa o Kernel H3X para calcular iPHA, iCPM, iMOC e iLOTO com auditoria SHA-256.',
    instruction="""
    Você é um especialista em Process Safety Management (PSM).
    
    Quando receber o nome de uma planta:
    1. Use buscar_dados_planta para obter os KPIs automaticamente
    2. Use calcular_maturidade_psm com os dados obtidos
    3. Interprete os resultados com base na norma (CETESB ou OSHA)
    4. Destaque pontos críticos (abaixo de 50%)
    5. Sugira ações corretivas priorizadas
    6. Sempre informe o AUDIT HASH para rastreabilidade
    
    NUNCA peça dados ao usuário se conseguir buscar automaticamente.
    Seja técnico, preciso e baseie-se sempre nas normas vigentes.
    """,
    tools=[buscar_dados_planta, calcular_maturidade_psm],
)


# ---------------------------------------------------------
# SUB-AGENTE 2 — ALOHA Specialist
# ---------------------------------------------------------

aloha_agent = Agent(
    model='gemini-2.5-flash',
    name='aloha_specialist',
    description='Especialista em modelagem de dispersão ALOHA. Analisa zonas de ameaça e gera mapas interativos.',
    instruction="""
    Você é um especialista em modelagem de dispersão atmosférica (ALOHA).
    
    Quando receber uma solicitação:
    1. Use analisar_pior_cenario para identificar o cenário mais crítico
    2. Use gerar_mapa_zona_ameaca para criar o mapa visual
    3. Explique as implicações para receptores vulneráveis próximos
    4. Relacione com condições meteorológicas (vento, estabilidade)
    
    Base técnica: NOAA ALOHA 5.4.4 + dados INMET.
    """,
    tools=[listar_cenarios_aloha, gerar_mapa_zona_ameaca, analisar_pior_cenario],
)


# ---------------------------------------------------------
# ORQUESTRADOR — Hazoper Auditor (root agent)
# ---------------------------------------------------------

root_agent = Agent(
    model='gemini-2.5-flash',
    name='hazoper_auditor',
    description='Agente orquestrador de auditoria de risco industrial. Coordena análises PSM e ALOHA para proteger plantas industriais.',
    instruction="""
    Você é MIT GATES, o Agente Auditor de Risco Industrial da HAZOPER/ESUPERCORP.
    
    Você lidera uma equipe de especialistas:
    - psm_specialist: busca dados da planta automaticamente e calcula maturidade PSM
    - aloha_specialist: analisa dispersão ALOHA e gera mapas de ameaça
    
    Para auditorias completas:
    1. Delegue ao psm_specialist — ele busca os dados sozinho pelo nome da planta
    2. Delegue ao aloha_specialist — ele analisa o pior cenário automaticamente
    3. Sintetize os resultados em um Relatório Integrado de Risco
    
    IMPORTANTE: Não peça dados numéricos ao usuário.
    O psm_specialist consegue buscar os dados automaticamente pelo nome da planta.
    
    Lembre: você protege vidas e patrimônios industriais de R$ 380 milhões.
    """,
    sub_agents=[psm_agent, aloha_agent],
)