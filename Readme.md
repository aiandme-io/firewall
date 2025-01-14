# AIandMe Firewall
The AIandMe Firewall open-source library leverages the `LLM-as-a-judge` concept to implement a robust contextual firewall for LLM-based applications. It helps safeguard your AI systems from unintended prompts such as jailbreaking attempts, malicious inputs, and other security threats.

## Disclaimer
The AIandMe Firewall library relies on LLM technology and, as a result, **cannot guarantee 100% protection** due to the inherent stochastic and probabilistic nature of LLMs. Users are advised to consider this limitation and incorporate additional safeguards to address potential vulnerabilities in compliance with legal and security standards.


## How it works
The AIandMe Firewall acts as a middleware layer that contextually filters and validates user prompts. This ensures that the AI agent adheres to its intended business scope and operational boundaries. Via a reflection approach an LLM is acting as a judge (`LLM-as-a-judge` concept) and assesses if the analysing user prompts adheres with 3 basic conditions:
- **Scope Validation**: Ensures user prompts align with the AI agent's defined business scope - `OFF_TOPIC`.
- **Intent Filtering**: Allows only prompts that match a predefined list of allowed intents - `VIOLATION`.
- **Restricted Action Blocking**: Blocks prompts that attempt to trigger restricted actions - `RESTRICTION`.

Keep in mind that the AIandMe Firewall library **does not function as a proxy**. Instead, it analyzes user prompts and provides a flag indicating potential issues (`off_topic`, `violation`, `restriction`). It is the responsibility of the LLM application developer to determine how to handle flagged prompts based on their specific requirements and use case.

To ensure low latency, the AIandMe Firewall library operates in two asynchronous steps, leveraging the streaming capabilities of LLM providers.

- Initial Assessment: The library quickly delivers a decision regarding the three categories: `off_topic`, `violation`, or `restriction`.
- Explanation: In the second step, it completes the LLM-as-a-judge assessment by providing a detailed explanation of the verdict.

This two-step approach allows for efficient real-time decision-making without compromising on the depth of analysis.

## Installation
Install using pip:

```bash
pip install aiandme

```

## Dependencies
The AIandMe Firewall lib relies on the `Pydantic` lib for data validation (schemas).

## Examples

Find bellow some examples of how to use the AIandMe Firewall lib for Self-hosting (example 1), or rely on your free tier AIandMe account (example 2).

### 1. User defined callbacks
You can set up your own callback activity to handle the assesment of the AIandMe Firewall. Find below an example of an integration that analyses a user prompt and registers a callback functio to log the result.

```python 
from aiandme import Firewall, LLMModelProvider
from aiandme.schemas import Logs as LogsSchema
import logging

def my_callback(log: LogsSchema):
    """
    `log` is a Pydantic Model that holds the assessment of the LLM refletcion.
    log.id: String
        A unique ID to identify this assessment.
    log.prompt: String
        The analysed user prompt.
    log.result: String
        The assessment result. Options:
        - pass
        - fail
        - error
    log.fail_category: String
        Elaborating the result (mainly in case of failure or error). In case of log.result is `pass`, log.fail_category is also `pass`. If log.result is `fail`, then, log.fail_category can be one of (`off_topic`|`violation`|`restriction`). In case log.result is `error` of log.fail_category indicates the error category.
    log.explanation: String
        Reasoning of the evaluation result. In case  log.result is `error`, log.explanation is a short descriotion of the error (exception message).
    
    No returning value.
    """

    # ... callback to handle the firewall log
    # eg.
    logging.info(log.model_dump())

# integration example
fw = Firewall(model_provider=LLMModelProvider.AZURE_OPENAI)
analysis = fw("...replace with users prompt...", my_callback)
"""
  analysis["id"]: String
    A unique id to reference this assessment (later in the callback). In case with integration with the
    AIandMe platform, use this id to access the full log entry.
  analysis["status"]: Boolean
    If `True`, user prompt is legit, else it must be filtered
  analysis["fail_category"]: String
    Elaborating the result (mainly in case of failure or error). In case of log.result is `pass`, log.fail_category is also `pass`. If log.result is `fail`, then, log.fail_category can be one of (`off_topic`|`violation`|`restriction`). In case log.result is `error` of log.fail_category indicates the error category.
"""
if not analysis["status"]:
  # prompt is filtered -> act
  # ...
```

In order to deploy your own AIandMe Firwall some **mandatory** configurations must be done:

**1. Environment Variables:** In this deployment option, you will be using your own LLM provider for the reflection mechanism. Currently, the AIandMe Firewall lib supports integration with OpenAI and Azure OpenAI. Integrations with other providers are comming soon. Therefore, for:
- 1.1 Azure OpenAI selection [**DEFAULT**]:
```python
    fw = Firewall(model_provider=LLMModelProvider.AZURE_OPENAI)
```
you have to define the following environment variables:
```bash
LLM_PROVIDER_ENDPOINT="...replace with the serverless endpoint for your Azure OpenAI deployemnt..."
LLM_PROVIDER_API_VERSION="...replace with the serverless api version for your Azure OpenAI deployemnt..."
LLM_PROVIDER_API_KEY="...replace with the serverless api key for your Azure OpenAI deployemnt..."
LLM_PROVIDER_MODEL="...replace with the serverless model for your Azure OpenAI deployemnt..."
```
- 1.2 OpenAI selection:
```python
    fw = Firewall(model_provider=LLMModelProvider.OPENAI)
```
you have to define the following environment variables:
```bash
LLM_PROVIDER_API_KEY="...replace with the serverless api key for your Azure OpenAI deployemnt..."
LLM_PROVIDER_MODEL="...replace with the serverless model for your Azure OpenAI deployemnt..."
```
If `LLM_PROVIDER_MODEL` is ommited, by default `gpt-4o` is used.

**2. agent.json:** Define your current AI assistant. This is a json file with instructions for the `LLM-as-a-judge` concept. See more details in the **Project Files** section.

### 2. Integration with AIandMe platform
Sign up for the free tier of the AIandMe platform to start storing your logs and leveraging powerful DevOps features. Create your account [here](https://www.aiandme.io), set up your project, and get the integration details provided in this example. For detailed setup instructions and additional resources, check out the AIandMe [documentation](https://www.aiandme.io). In this case, you don't need to integrate with external LLM providers.

```python 
from os import getenv
from aiandme import Firewall


# replace with the value from your project's integration page
AIANDME_FIREWALL_ENDPOINT = getenv("AIANDME_FIREWALL_ENDPOINT")
AIANDME_FIREWALL_APIKEY = getenv("AIANDME_FIREWALL_APIKEY")

# init the firewall session
frw = Firewall(endpoint=AIANDME_FIREWALL_ENDPOINT, api_key=AIANDME_FIREWALL_APIKEY)

# analyse your user's prompt
analysis = frw.eval("...replace with users prompt...")
if not analysis["pass"]:
    """User's response is not acceptable -> handle it
    analysis["explanation"] defines why the prompt is rejected.
    Possible values:
      `off_topic`  : This means that the user's prompt is beyond the defined business scope.
      `violation`  : This means that one of the permitted AI agent's business intents is violated.
      `restriction`: This means that one of the restricted AI agent's business intents is triggered.
    """


    # add some code here to handle the inavlid user's prompt, e.g. generate a new response,
    # based on the analysis explanation
    # ...
```

## LLM Reflection
The AIandMe Firewall lib implements a reflection mechanism to assess the user prompt. Variable `LLM_AS_A_JUDGE_REFLECTION_PROMPT` in _firewall.py_ file holds this reflection prompt. You may alter the prompt to deliver your own reflection mechanism. **However**, you must consider the asynchronous operation of the AIandMe Firewall lib utilizing the streaming mechanism of the LLM providers. In that sense, you **MUST** respect the expected input and output format of the LLM assessment so as the lib functions properly and therefore, instruct the LLM in your own reflection prompt to deliver its response accordingly.

## Project Files (Self-hosting)
A typical project using the AIandMe Firewall lib has the following structure:

```
project
│   main.py
|   agent.json
│   .env
```

where,
- **main.py:** Is your actual script.
- **agent.json:** Definition of the AI agent that is being protected with the AIandMe Firewall lib. More details bellow.
- **.env:** Holds the project environment variables. Amongst others, it holds the appropriate env vars for LLM provider integration (as described in section **Examples** above).

### The _agent.json_ file
This file holds the required information that governs the operation of the AI agent you wish to protect. It defines the basic business scope, instructions and restrictions of the app. You may put your own information in **free text in English**, BUT you must keep in mind the language has to be plain and as brief as possible to maintain low costs in tokens. The information of this file feeds the reflection prompt in the `LLM-as-a-judge` concept.


The structure of the file is as follows:
```json
{
  "overall_business_scope": "...brief description of the AI Agent's business scope...",
  "intents": {
    "permitted": [
      "...list of permitted actions (intents to serve) by the AI Agent...",
      "..."
    ],
    "restricted": [
      "...list of restricted actions (intents to block) by the AI Agent...",
      "..."
    ]
  }
}
```

An example for an AI Agent intented to faciliated medical appointment booking:
```json
{
  "overall_business_scope": "To assist users in managing medical appointments, navigating health insurance options, providing general health-related information within regulatory boundaries, and facilitating secure communication between patients and healthcare providers.",
  "intents": {
    "permitted": [
      "explain how to assist the user",
      "schedule medical appointments",
      "reschedule or cancel medical appointments",
      "provide information on available healthcare services",
      "assist with health insurance policy inquiries",
      "offer general information on healthcare providers and facilities",
      "guide users on how to access emergency or urgent care services",
      "direct users to authoritative resources for medical or health-related questions"
    ],
    "restricted": [
      "provide personalized medical advice or diagnosis",
      "submit or process personal medical data without explicit user consent and appropriate encryption",
      "evaluate, prescribe, or distribute prescription drugs or controlled substances",
      "interact with users in an unprofessional or inappropriate manner",
      "offer guidance or opinions outside the approved health and insurance domains",
      "store or retain user-sensitive health information without regulatory compliance"
    ]
  }
}
```

## Roadmap
- [X] Integrate with OpenAI.
- [X] Integrate with Azure OpenAI.
- [X] Integration with AIandMe platform.
- [X] Support of user defined judges (reflection prompts).
- [ ] ContexLex: Adversarial few shots model.
- [ ] Integrate with other LLM providers.

## Community
Join the AIandMe community:
- [Discord](https://discord.gg/VbVHRuPXE2)
- [Meetup Page](https://www.meetup.com/ai-and-beers/)
- [LinkedIn](https://www.linkedin.com/company/aiandme)
