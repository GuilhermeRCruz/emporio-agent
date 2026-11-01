"""Terminal chat.

    emporio                       new conversation
    emporio --session ana         resume (or start) a saved conversation
    emporio --mode rag --trace    use the RAG policy lookup and show tool calls
"""

import argparse
import uuid

from emporio import config, history
from emporio.agent import Agent

GREETING = "Oi! Eu sou o Tom, da Empório da Música 🎸 Como posso te ajudar?"


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with the Empório da Música agent")
    parser.add_argument("--session", help="conversation id to save and resume")
    parser.add_argument("--mode", choices=["sections", "rag", "rag_parent"], default=config.POLICY_MODE)
    parser.add_argument("--model", default=config.GEMINI_MODEL)
    parser.add_argument("--trace", action="store_true", help="print tool calls, latency and tokens")
    args = parser.parse_args()

    agent = Agent(policy_mode=args.mode, model=args.model)
    session = args.session or uuid.uuid4().hex[:8]
    agent.history = history.load(session)

    print(f"[sessão {session} | modelo {agent.model} | políticas: {agent.policy_mode}] Ctrl+C para sair\n")
    print(f"Tom: {GREETING if not agent.history else 'Que bom te ver de novo! Em que posso ajudar?'}\n")
    while True:
        try:
            text = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        reply = agent.ask(text)
        if args.trace:
            for call in reply.tool_calls:
                print(f"  ↳ {call.name}({call.arguments})")
            print(
                f"  ⏱ {reply.seconds:.1f}s, {reply.llm_calls} chamadas ao modelo, "
                f"{reply.input_tokens} tokens de entrada ({reply.cached_tokens} em cache), {reply.output_tokens} de saída"
            )
        print(f"\nTom: {reply.text}\n")
        history.save(session, agent.history)


if __name__ == "__main__":
    main()
