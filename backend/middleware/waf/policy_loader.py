import os
import yaml
from typing import List, Dict

class PolicyLoader:
    def __init__(self, policies_dir: str):
        self.policies_dir = policies_dir
        self.policies: List[Dict] = []
        self._load_policies()

    def _load_policies(self):
        if not os.path.exists(self.policies_dir):
            print(f"[WAF] Warning: Policies directory {self.policies_dir} not found.")
            return

        for filename in os.listdir(self.policies_dir):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                filepath = os.path.join(self.policies_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        policy = yaml.safe_load(f)
                        if policy and policy.get('is_active', False):
                            self.policies.append(policy)
                except Exception as e:
                    print(f"[WAF] Error loading policy {filename}: {e}")
        
        print(f"[WAF] Loaded {len(self.policies)} active policies.")

    def get_policies_for_agent_and_tool(self, agent_id: str, tool_name: str) -> List[Dict]:
        matched = []
        for p in self.policies:
            p_agent = p.get('agent_id', 'any')
            p_tool = p.get('tool_name', 'global')
            
            agent_match = p_agent in ['any', 'agent_any'] or p_agent == agent_id
            tool_match = p_tool == 'global' or p_tool == tool_name
            
            if agent_match and tool_match:
                matched.append(p)
        return matched
