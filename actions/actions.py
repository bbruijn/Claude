import os
import base64
import requests
from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

VENICE_API_URL = "https://api.venice.ai/api/v1/image/generate"
VENICE_API_KEY = os.environ.get("VENICE_API_KEY", "")


class ActionGenerateImage(Action):

    def name(self) -> Text:
        return "action_generate_image"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_message = tracker.latest_message.get("text", "")

        # Extract the image description from the user's message
        prompt = self._extract_prompt(user_message)

        if not prompt:
            dispatcher.utter_message(
                text="I'd be happy to generate an image! Please describe what you'd like, e.g. 'generate an image of a sunset over the ocean'."
            )
            return []

        if not VENICE_API_KEY:
            dispatcher.utter_message(
                text="Image generation is not configured. The VENICE_API_KEY environment variable is missing."
            )
            return []

        dispatcher.utter_message(text=f"Generating an image of: {prompt}...")

        try:
            response = requests.post(
                VENICE_API_URL,
                headers={
                    "Authorization": f"Bearer {VENICE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "fluently-xl",
                    "prompt": prompt,
                    "width": 1024,
                    "height": 1024,
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()

            images = data.get("images", [])
            if images:
                b64_image = images[0]
                data_url = f"data:image/png;base64,{b64_image}"
                dispatcher.utter_message(image=data_url)
            else:
                dispatcher.utter_message(
                    text="Sorry, the image generation service did not return an image. Please try again."
                )
        except requests.exceptions.Timeout:
            dispatcher.utter_message(
                text="The image generation request timed out. Please try again."
            )
        except requests.exceptions.RequestException as e:
            dispatcher.utter_message(
                text="Sorry, I couldn't generate the image right now. Please try again later."
            )

        return []

    def _extract_prompt(self, message: str) -> str:
        """Extract the image description from the user message."""
        lower = message.lower()
        prefixes = [
            "generate an image of ",
            "generate image of ",
            "create an image of ",
            "create image of ",
            "make an image of ",
            "make image of ",
            "draw ",
            "paint ",
            "create a picture of ",
            "generate a picture of ",
            "make a picture of ",
            "picture of ",
            "image of ",
            "generate ",
            "create ",
            "make ",
        ]
        for prefix in prefixes:
            if lower.startswith(prefix):
                return message[len(prefix):].strip()
        return message.strip()
