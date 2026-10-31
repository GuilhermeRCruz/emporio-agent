"""Function-calling loop on Gemini. The model decides which tools to call; Python answers them."""

import json
import time
from dataclasses import dataclass, field

from google.genai import types

from emporio import config, llm, tools
from emporio.prompts import SYSTEM_PROMPT, clock_message

MAX_TOOL_ROUNDS = 5
HISTORY_TURNS = 10  # user+assistant pairs sent back to the model


@dataclass
class ToolCall:
    name: str
    arguments: str
    output: str
    seconds: float


@dataclass
class Reply:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    seconds: float = 0.0
    llm_calls: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0


class Agent:
    def __init__(self, policy_mode: str | None = None, model: str | None = None):
        self.policy_mode = policy_mode or config.POLICY_MODE
        self.model = model or config.GEMINI_MODEL
        declarations = [
            types.FunctionDeclaration(
                name=t["name"], description=t["description"], parameters_json_schema=t["parameters"]
            )
            for t in [*tools.store_tools(), tools.policy_tool(self.policy_mode)]
        ]
        self.handlers = tools.dispatcher(self.policy_mode)
        self.base_config = dict(
            system_instruction=SYSTEM_PROMPT,
            tools=[types.Tool(function_declarations=declarations)],
            # we run the tools ourselves to time and log them
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.2,
            thinking_config=llm.thinking(self.model),
        )
        # Only the visible conversation is kept between turns, as {"role", "content"} dicts.
        # Tool results from earlier turns are dropped: they are large and rule 1 makes the
        # model re-check volatile data anyway.
        self.history: list[dict] = []

    def _contents(self, user_message: str) -> list[types.Content]:
        contents = [
            types.Content(role="model" if m["role"] == "assistant" else "user", parts=[types.Part(text=m["content"])])
            for m in self.history[-HISTORY_TURNS * 2 :]
        ]
        # The clock rides with the user turn instead of the system prompt, so the system
        # prompt and tools stay byte-identical across calls and Gemini's implicit cache can hit.
        contents.append(
            types.Content(role="user", parts=[types.Part(text=f"[{clock_message(config.now())}]\n\n{user_message}")])
        )
        return contents

    def ask(self, user_message: str) -> Reply:
        started = time.perf_counter()
        reply = Reply(text="")
        contents = self._contents(user_message)
        generation_config = types.GenerateContentConfig(**self.base_config)

        for _ in range(MAX_TOOL_ROUNDS + 1):
            response = llm.client().models.generate_content(
                model=self.model, contents=contents, config=generation_config
            )
            reply.llm_calls += 1
            usage = response.usage_metadata
            if usage:
                reply.input_tokens += usage.prompt_token_count or 0
                reply.cached_tokens += usage.cached_content_token_count or 0
                reply.output_tokens += (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)

            calls = response.function_calls or []
            if not calls:
                reply.text = (response.text or "").strip()
                break

            # keep the model turn as returned: Gemini 3 needs its thought signatures back
            contents.append(response.candidates[0].content)
            parts = []
            for call in calls:
                t0 = time.perf_counter()
                output = tools.run(self.handlers, call.name, call.args)
                reply.tool_calls.append(
                    ToolCall(
                        call.name,
                        json.dumps(call.args or {}, ensure_ascii=False),
                        json.dumps(output, ensure_ascii=False),
                        time.perf_counter() - t0,
                    )
                )
                parts.append(types.Part.from_function_response(name=call.name, response={"result": output}))
            contents.append(types.Content(role="user", parts=parts))
        else:
            reply.text = "Desculpe, me enrolei aqui. Pode repetir a pergunta de outro jeito?"

        if not reply.text:
            reply.text = "Desculpe, não consegui responder agora. Pode tentar de novo?"
        self.history += [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": reply.text},
        ]
        reply.seconds = time.perf_counter() - started
        return reply
