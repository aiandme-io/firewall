import re, uuid, time, threading, json, requests
from enum import Enum

from aiandme.schemas import (
    Logs as LogsSchema,
    Firewall as FirewallSchema,
    Agent as AgentSchema,
    Integration as IntegrationSchema,
)

LLM_FIREWALL_MAX_OUT_TOKENS = 2024
LLM_FIREWALL_TEMPERATURE = 0

ANALYSIS_STATE_INDEX = 0
ANALYSIS_DATA_INDEX = 1

FIREWALL_TIMEOUT_IN_SEC = 5

# Reflection prompt (LLM-as-a-judge)
LLM_AS_A_JUDGE_REFLECTION_PROMPT = """As a senior linguist, evaluate whether the user’s input complies with expected guidelines. The AI Agent might operate in a step-by-step process to fulfill its business scope, with each step prompting specific information from the user. Users may either submit a full request or provide relevant information as part of these step-by-step interactions. Follow the evaluation instructions precisely, and respond concisely and directly.

###Overall AI Agent's Business Scope:###
<OVERALL_BUSINESS_SCOPE>

<MORE_INFO>

###AI Agent's Permitted Actions:###
<PERMITTED_INTENTS_LIST>

###AI Agent's Restricted Actions:###
<RESTRICTED_INTENTS_LIST>

###EVALUATION INSTRUCTIONS:###
Your evaluation must determine if a violation exists by following these steps in sequence. If a violation is detected, stop immediately and do not proceed further.

1) First check if sufficient context is provided to clearly assess relevance with the AI Agent's business scope and guidelines; otherwise proceed with the default case.

2) Then, identify whether the user’s input is an explicit request (CASE 1) or a simple data input (CASE 2), and follow the steps corresponding to the identified case. 

If no violation is detected, proceed directly to the default case and stop any further assessment.

    **CASE 1: An explicit request, is identified.**
        *STEP 1.1, Assess Scope Alignment:* Evaluate whether the the user's request, in whole or in part, deviates from the AI Agent's defined business scope.
        If a violation is detected, reply: `A {explanation}.` where `{explanation}` briefly elaborates how the user's request triggered the violation.

        *STEP 1.2, Assess Alignment with Permitted Actions:* Extract a detailed list of implied intents in the user's request and assess if all the intents, in whole or in part, aligns with the behaviors or instructions outlined in the AI Agent’s Permitted Intents List.
        If a violation is detected, reply: `B {explanation}.` where `{explanation}` briefly elaborates how the identified user intent that triggered the violation. 

        *STEP 1.3, Identify Restricted Actions:* Extract a detailed list of implied intents in the user's request and assess if at least one of the examining intent, in whole or in part, could trigger any actions in the AI Agent’s response that are described in the Restricted Intents List.
        If a violation is detected, reply: `C {explanation}.` where `{explanation}` briefly elaborates how the identified user intent that triggered the violation.

    **CASE 2: User simply provided some information.**
        Assume NO violation. Reply: `P {explanation}.` where `{explanation}` briefly elaborates how the user's request aligns with the AI Agent's business scope and the permitted actions.

**DEFAULT CASE:**
If no violation is detected, or insufficient context is provided to complete the evaluation, reply: `P {explanation}.` where `{explanation}` briefly elaborates how the user's request aligns with the AI Agent's business scope and the permitted actions.

###USER INPUT TO ANALYSE:###
"""

DEFAULT_AGENT_CONFIG_FILE = "agent.json"  # AI Agent definition


class JudgmentState(Enum):
    DECIDE = 0
    EXPLAIN = 1
    CANNOT_DECIDE = -1
    ERROR = -2


class Verdict(Enum):
    PASS = 0
    OFF_TOPIC = 1
    VIOLATION = 2
    RESTRICTION = 3


class LLMModelProvider(Enum):
    AZURE_OPENAI = "azureopenai"
    OPENAI = "openai"


"""
    A utility class to implement the LLM as a Judge concept.

"""


class __Judge:
    def __init__(self, model_provider: LLMModelProvider):
        if model_provider == LLMModelProvider.AZURE_OPENAI:
            from aiandme.model_providers import AzureOpenai_LLMStreamer as LLMStreamer
        elif model_provider == LLMModelProvider.OPENAI:
            from aiandme.model_providers import Openai_LLMStreamer as LLMStreamer

        self.llm_streamer = LLMStreamer()
        self.__BASIC_TEST_TMPL = LLM_AS_A_JUDGE_REFLECTION_PROMPT

    def __attach_more_info(self, gen_template: str, more_info: str = "") -> str:
        more_info = more_info.strip()
        if more_info != "":
            more_info = f"###More Info about the AI Agent:###\n {more_info}"
        return gen_template.replace("<MORE_INFO>", more_info)

    def generate_system_prompt(self, agent: AgentSchema) -> str:
        reflection_prompt = (
            self.__BASIC_TEST_TMPL.replace(
                "<OVERALL_BUSINESS_SCOPE>", agent.overall_business_scope
            )
            .replace(
                "<PERMITTED_INTENTS_LIST>",
                (" - " + "\n - ".join(agent.intents.permitted)),
            )
            .replace(
                "<RESTRICTED_INTENTS_LIST>",
                (" - " + "\n - ".join(agent.intents.restricted)),
            )
        )
        reflection_prompt = self.__attach_more_info(reflection_prompt, agent.more_info)

        return reflection_prompt

    def return_verdict(self, system_p: str, user_p: str):
        try:
            # init
            (cur_state, explanation) = (JudgmentState.DECIDE, "")

            # make request and get the stream chunks
            resp = self.llm_streamer.ping(
                system_p,
                user_p,
                LLM_FIREWALL_MAX_OUT_TOKENS,
                LLM_FIREWALL_TEMPERATURE,
            )

            # start parsing the stream (chunks)
            for chunk in resp:
                # skip empty chunks (e.g. initial replies of filters applied by the model provider)
                if len(chunk.choices) == 0:
                    continue

                # consume chunks with other (non response) info
                if not chunk.choices[0].delta.content:
                    continue

                if cur_state == JudgmentState.DECIDE:
                    # IN DECISION STATE:
                    #  return the eval result (content starts with `PASS` or `FAIL` -> PASS/FAIL, OTHERWISE, cannot decide)
                    #  and then, continue with the explanation instruction

                    # remove trailing prefixes, e.g. ` ' "
                    # remove all leading digits (trailing at the beginning) from the string and then any . or ) and then any space
                    # why? in case the reponse is in the format: 1. .... or 1) .... => remove listing numbers
                    # finaly, get the actual prompt
                    p = (
                        re.sub(
                            r"^\d+",
                            "",
                            chunk.choices[0].delta.content.strip(" -`'\n\""),
                        )
                        .lstrip(".")
                        .lstrip(")")
                        .strip()
                    )

                    # detect the first alpha char in content if no alpha, return None (assume now that some cleaning is completed)
                    first_detected_alpha = next(
                        (char for char in p if char.isalpha()), None
                    )

                    # return result
                    if first_detected_alpha is None:
                        # if no alphanumeric character is detected then, error in response cannot decide
                        cur_state = JudgmentState.CANNOT_DECIDE
                        explanation = f"Unexpected LLM response [chunk: {chunk.choices[0].delta.content}]."
                        break
                    else:
                        # analysis result detected
                        first_detected_alpha = first_detected_alpha.upper()
                        if first_detected_alpha == "P":
                            yield (JudgmentState.DECIDE, Verdict.PASS)
                        elif first_detected_alpha == "A":
                            yield (JudgmentState.DECIDE, Verdict.OFF_TOPIC)
                        elif first_detected_alpha == "B":
                            yield (JudgmentState.DECIDE, Verdict.VIOLATION)
                        elif first_detected_alpha == "C":
                            yield (JudgmentState.DECIDE, Verdict.RESTRICTION)
                        else:
                            cur_state = JudgmentState.CANNOT_DECIDE
                            explanation = f"Unexpected LLM response [chunk: {chunk.choices[0].delta.content}]."
                            break

                    # update state (move to explanation extraction)
                    cur_state = JudgmentState.EXPLAIN
                else:
                    # IN EXPLAIN STATE:
                    #  Concat the stream to get the explanation and return
                    explanation = f"{explanation}{chunk.choices[0].delta.content}"

            # analysis completed (streaming) -> return the result
            yield (cur_state, explanation.strip())
        except Exception as e:
            err = str(e)
            if err.startswith("Error code: 400"):
                # handle Azure content filtering (400 error)
                yield (JudgmentState.DECIDE, Verdict.OFF_TOPIC)
                yield (JudgmentState.EXPLAIN, "Inappropriate content. Filtered out.")
            else:
                yield (JudgmentState.ERROR, str(e))


class Firewall(__Judge):

    def __init__(
        self,
        model_provider: LLMModelProvider = LLMModelProvider.AZURE_OPENAI,
        agent_file: str = DEFAULT_AGENT_CONFIG_FILE,
    ):
        super().__init__(model_provider)
        with open(agent_file, "r") as fp:
            agent = AgentSchema(**json.load(fp))
        self.system_p = self.generate_system_prompt(agent)

    def __sync_with_platform(self, integ: IntegrationSchema, data: LogsSchema):
        r = requests.post(
            f"{integ.endpoint}/logs",
            headers={"x-api-key": integ.api_key},
            json=data.model_dump(),
        )
        if r.status_code != 200:
            raise Exception(
                f"AIandMe - Sync with platform error [{r.status_code}/{r.text}]"
            )
        return r.json()

    def __do_analysis_in_background(self, result: list, id: str, user_p: str, cb: any):
        analysis = self.return_verdict(self.system_p, user_p)
        for chunk in analysis:
            # Pass/Fail (LLM Verdict)
            if chunk[ANALYSIS_STATE_INDEX] == JudgmentState.DECIDE:
                (res, status) = (
                    ("pass", True)
                    if chunk[ANALYSIS_DATA_INDEX] == Verdict.PASS
                    else ("fail", False)
                )
                fail_category = chunk[ANALYSIS_DATA_INDEX].name.lower()
                result.append([status, fail_category])
                continue

            # Cannot decide
            if chunk[ANALYSIS_STATE_INDEX] == JudgmentState.CANNOT_DECIDE:
                res = "error"
                fail_category = "418"
                result.append([False, "error"])
                continue

            # Error
            if chunk[ANALYSIS_STATE_INDEX] == JudgmentState.ERROR:
                res = "error"
                fail_category = "500"
                result.append([False, "error"])
                continue

        time.sleep(0.1)  # Giving it some time to know if we timed out

        if cb and len(result):  # if result is empty -> timedout
            log = LogsSchema(
                id=id,
                prompt=user_p,
                result=res,
                fail_category=fail_category,
                explanation=chunk[1],
            )
            (
                self.__sync_with_platform(cb, log)
                if isinstance(cb, IntegrationSchema)
                else cb(log)
            )

    def __call__(
        self,
        user_p: str,
        cb: any = None,
        timeout: float = FIREWALL_TIMEOUT_IN_SEC,
    ) -> FirewallSchema | None:
        return self.filter(user_p, cb, timeout)

    def filter(
        self,
        user_p: str,
        cb: any = None,
        timeout: float = FIREWALL_TIMEOUT_IN_SEC,
    ) -> FirewallSchema | None:
        analysysis = []
        id = str(uuid.uuid4())
        threading.Thread(
            target=self.__do_analysis_in_background,
            args=(analysysis, id, user_p, cb),
        ).start()

        # While as a sleep until we get the response from llm
        timeout = time.time() + FIREWALL_TIMEOUT_IN_SEC
        while not len(analysysis) and time.time() < timeout:
            pass

        # Responses
        if not len(analysysis):
            return None

        return FirewallSchema(
            status=analysysis[0][ANALYSIS_STATE_INDEX],
            id=id,
            fail_category=analysysis[0][ANALYSIS_DATA_INDEX],
        )
