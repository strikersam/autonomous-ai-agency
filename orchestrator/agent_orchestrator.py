import requests

class AgentOrchestrator:
    def __init__(self, claude_url, api_key):
        self.claude_url = claude_url
        self.api_key = api_key

    def deploy_agent(self, agent_config):
        headers = {'Authorization': f'Bearer {self.api_key}'}
        response = requests.post(f'{self.claude_url}/agents', json=agent_config, headers=headers)
        if response.status_code == 201:
            return response.json()['agent_id']
        else:
            raise Exception('Failed to deploy agent')

    def list_agents(self):
        headers = {'Authorization': f'Bearer {self.api_key}'}
        response = requests.get(f'{self.claude_url}/agents', headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception('Failed to list agents')