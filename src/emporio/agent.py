"""Function-calling loop. The model decides which tools to call; Python answers them."""

import time
from dataclasses import dataclass, field

from openai import OpenAI

from emporio import config, tools
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
    def __init__(self, policy_mode: str | None = None, model: str | None = None, client: OpenAI | None = None):
        self.policy_mode = policy_mode or config.POLICY_MODE
        self.model = model or config.OPENAI_MODEL
        self.client = client or OpenAI()
        self.tools = [*tools.store_tools(), tools.policy_tool(self.policy_mode)]
        self.handlers = tools.dispatcher(self.policy_mode, self.client)
        # Only the visible conversation is kept between turns. Tool results from earlier
        # turns are dropped: they are large and rule 1 makes the model re-check volatile data.
        self.history: list[dict] = []

    def _completion(self, messages: list[dict]):
        kwargs = {}
        if not self.model.startswith(("gpt-5", "o")):
            kwargs["temperature"] = 0.2  # reasoning models only accept the default
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.tools,
            parallel_tool_calls=True,
            prompt_cache_key="emporio-agent",
            **kwargs,
        )

    def ask(self, user_message: str) -> Reply:
        started = time.perf_counter()
        reply = Reply(text="")
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self.history[-HISTORY_TURNS * 2 :],
            {"role": "system", "content": clock_message(config.now())},
            {"role": "user", "content": user_message},
        ]

        for _ in range(MAX_TOOL_ROUNDS + 1):
            response = self._completion(messages)
            reply.llm_calls += 1
            if response.usage:
                reply.input_tokens += response.usage.prompt_tokens
                reply.output_tokens += response.usage.completion_tokens
                details = response.usage.prompt_tokens_details
                reply.cached_tokens += (details.cached_tokens or 0) if details else 0

            message = response.choices[0].message
            if not message.tool_calls:
                reply.text = (message.content or "").strip()
                break

            messages.append(message.model_dump(exclude_none=True))
            for call in message.tool_calls:
                t0 = time.perf_counter()
                output = tools.run(self.handlers, call.function.name, call.function.arguments)
                reply.tool_calls.append(
                    ToolCall(call.function.name, call.function.arguments, output, time.perf_counter() - t0)
                )
                messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
        else:
            reply.text = "Desculpe, me enrolei aqui. Pode repetir a pergunta de outro jeito?"

        self.history += [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": reply.text},
        ]
        reply.seconds = time.perf_counter() - started
        return reply
