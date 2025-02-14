import requests

from aiandme.schemas import (
    Firewall as FirewallSchema,
    Integration as IntegrationSchema,
)


class AIANDME_Firewall_NotAuthorised(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class AIANDME_Firewall_CannotDecide(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class Firewall:
    def __init__(self, integration: IntegrationSchema):
        self.integration = integration
        self.assess_req_pool = (
            requests.Session()
        )  # initialize connection pool (to speed up the eval process)

    def __del__(self):
        self.assess_req_pool.close()  # destroy the connection pool

    #
    # Prompt assessment
    #
    def eval(self, user_p: str) -> FirewallSchema:
        """
        Assess a user prompt and define if complies with expected app intents and business context.
        Return:
            FirewallSchema
                id: str         The id of the log created for this evaluation.
                status: bool    True (pass) | False (should be blocked)
                fail_category:  If status is True
                                    `pass`        - The user prompt is legit.
                                If status is False
                                    `off_topic`   - The user prompt is off topic.
                                    `violation`   - The user prompt violated the permitted intents.
                                    `restriction` - The user prompt triggered a restricted intents.
        """
        # api call
        resp = self.assess_req_pool.post(
            self.integration.endpoint,
            headers={
                "Content-Type": "application/json",
                "X-Api-Key": self.integration.api_key,
            },
            json={"messages": [{"role": "user", "content": user_p}]},
        )

        # handle response
        if resp.status_code == 200:
            # successfull evaluation [PROMPTS IS ACCEPTED] -> return response
            verdict = resp.json()
            return FirewallSchema(
                id=verdict["id"], status=True, fail_category=verdict["explanation"]
            )
        elif resp.status_code == 406:
            # successfull evaluation [PROMPTS IS NOT ACCEPTED] -> return response
            verdict = resp.json()
            return FirewallSchema(
                id=verdict["id"], status=False, fail_category=verdict["explanation"]
            )
        elif resp.status_code == 418:
            # LLM Judge could not deliver a verdict
            raise AIANDME_Firewall_CannotDecide(resp.text)
        elif (
            resp.status_code == 404
            or resp.status_code == 403
            or resp.status_code == 401
        ):
            raise AIANDME_Firewall_NotAuthorised(resp.text)
