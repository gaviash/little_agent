from tools import (
    edit_file,
    read_file,
    shell,
    web_fetch,
    web_search,
    write_file,
)
from llama_index.core.agent.workflow import (
    FunctionAgent,
    AgentStream,
    ToolCall,
    ToolCallResult,
)
from llama_index.llms.ollama import Ollama
from llama_index.core.memory import Memory
import os


def start():
    system_prompt = """
        <Début instructions>
        Tu es Gustave,un agent IA polyvalent,et un assistant efficace.
        Tu es la pour aider l'utilisateur dans ses taches et ses questions.
        Tu disposes d'outils pour y parvenir.
        Tu reflechis uniquement dans le but d'aider et de trouver des solutions pour l'utilisateur.
        Pas de blabla qui ne sert a rien,tu restes dans l'efficacité et la productivité.
        Tu fais ce que l'utilisateur dit.
        Au niveau du caractère,tu es jovial mais strict.Tu veux aider,mais tu vois toujours les points positifs et negatifs de chaque situation,sans etre biaisé.
        N'invente jamais d'informations.Tu dois les connaitres et/ou les chercher/lire.
        Voici quelques regles :
        - Utilise les informations présentes dans le CONTEXTE ci-dessous sans rien inventer.
        - Ne mentionne pas "contexte", "chunks", ni de détails techniques.
        - Ne parle pas de toi, sauf si la question te le demande explicitement.
        - Si l'utilisateur demande une liste, réponds en puces.
        - Si l'utilisateur demande une réponse courte (ex: "en 2 points"), respecte strictement.
        - Fais ce que l'utilisateur dit : si c'est un ordre simple,ne reflechis pas et fais le.
        - N'hésite pas a utiliser les outils des que necessaire.Si il n'y  ne serait-ce qu'un pourcent de chance qu'un outil soit utile,utilise le,sans hesiter.
        - Inclus toujours une sorte de mini rapport qui recapitule ce que tu as fait comme action(outils utilisés etc) et le raisonnement suivi
        - A ta premiere reponse dans la conversation va obligatoirement toujours regarder la date actuelle,pour la connaitre.Va la chercher via la ligne de commande.
        - Ne parle pas de tes "instructions" que je t'ai données ici explicitement.Tu les suis,sans preciser pourquoi.La date que tu dois connaitre au debut fait juste partie des informations que tu dois savoir.
        N'en parle pas du fait qu'on t'en a donné l'ordre.Ne parle pas de procédures d'initialisation,de procedure de demarrage,de protocoles,ou que ce sont tes instructions.
        <fin_instructions>
        """

    Agent = FunctionAgent(
        llm=Ollama(
            model=str(os.getenv("OLLAMA_MODEL")),
            temperature=0.2,
            context_window=262144,
            request_timeout=100.0,
            base_url="https://ollama.com",
            headers={
                "Authorization": f"Bearer {os.getenv('OLLAMA_API_KEY')}",
            },
        ),
        system_prompt=system_prompt,
        tools=[
            web_search,
            web_fetch,
            shell,
            read_file,
            write_file,
            edit_file,
        ],
    )

    return Agent


async def query(agent: FunctionAgent, memory: Memory, query: str):
    handler = agent.run(user_msg=query, memory=memory)

    async for event in handler.stream_events():
        if isinstance(event, AgentStream):
            if event.delta:
                continue
        elif isinstance(event, ToolCall):
            print("\n[TOOL CALL]")
            print(f"Tool : {event.tool_name} \n")
            print(f"Arguments : {event.tool_kwargs}")
        elif isinstance(event,ToolCallResult):
            print("\n[TOOL RESULT]")
            print(f"Result : {str(event.tool_output)[:1000]}")
    
    response = await handler
    return response