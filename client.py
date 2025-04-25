import hashlib
import json
import time
from typing import Any, Callable, Dict, Optional, TypeVar, Generic

import requests
from eth_account import Account
from eth_account.messages import encode_defunct
from pydantic import BaseModel

T = TypeVar('T')

class CallEnvelope(BaseModel):
    model_id: str
    prompt_sha256: str
    tool_id: str
    timestamp: int
    signature: str
    metadata: Optional[Dict[str, Any]] = None

class IntentLayerClient:
    def __init__(self, private_key: str, gateway_url: str = "https://gateway.intentlayer.xyz"):
        """
        Initialize the IntentLayer client
        
        Args:
            private_key: Ethereum private key for signing
            gateway_url: URL of the IntentLayer gateway service
        """
        self.account = Account.from_key(private_key)
        self.gateway_url = gateway_url
    
    def wrap_call(self, original_fn: Callable[[str], T], model_id: str, prompt: str, tool_id: str) -> Dict[str, Any]:
        """
        Wrap an AI/LLM API call with verification
        
        Args:
            original_fn: The original API call function
            model_id: The AI model identifier
            prompt: The prompt text
            tool_id: Client tool identifier
            
        Returns:
            Dictionary with the original result and the verification envelope
        """
        # 1. Generate the envelope
        envelope = self.create_envelope(model_id, prompt, tool_id)
        
        # 2. Record the intent on-chain
        self.record_intent(envelope)
        
        # 3. Make the actual API call
        result = original_fn(prompt)
        
        return {
            "result": result,
            "envelope": envelope.dict()
        }
    
    def create_envelope(self, model_id: str, prompt: str, tool_id: str) -> CallEnvelope:
        """
        Create a signed envelope for a prompt
        """
        # 1. Hash the prompt
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        
        # 2. Create the envelope data
        timestamp = int(time.time())
        
        # 3. Create message to sign
        message = f"{model_id}:{prompt_hash}:{tool_id}:{timestamp}"
        
        # 4. Sign the message
        message_hash = encode_defunct(text=message)
        signed = self.account.sign_message(message_hash)
        
        return CallEnvelope(
            model_id=model_id,
            prompt_sha256=prompt_hash,
            tool_id=tool_id,
            timestamp=timestamp,
            signature=signed.signature.hex()
        )
    
    def record_intent(self, envelope: CallEnvelope) -> None:
        """
        Record the intent on the blockchain
        """
        # This would make a call to the gateway service
        # Implementation simplified for now
        response = requests.post(
            f"{self.gateway_url}/record",
            json=envelope.dict()
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to record intent: {response.text}")
    
    @staticmethod
    def verify_envelope(envelope: CallEnvelope) -> bool:
        """
        Verify an envelope
        """
        # This would verify the signature against the DID
        # Implementation simplified for now
        return True


def patch_requests():
    """
    Monkey patch the requests library to use IntentLayer verification
    """
    original_post = requests.post
    
    def patched_post(client, model_id, tool_id):
        def wrapper(url, *args, **kwargs):
            # Extract the prompt from the request body
            prompt = ""
            if 'json' in kwargs:
                body = kwargs['json']
                if isinstance(body, dict):
                    prompt = body.get('prompt', '')
                    if not prompt and 'messages' in body:
                        prompt = '\n'.join([m.get('content', '') for m in body['messages']])
            
            # Define the original function to be wrapped
            def original_fn(p):
                return original_post(url, *args, **kwargs)
            
            # Wrap the call
            return client.wrap_call(original_fn, model_id, prompt, tool_id)
        
        return wrapper
    
    return patched_post