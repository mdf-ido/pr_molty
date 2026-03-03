import os
import json
import time
import logging
import re
import random
from datetime import datetime, timedelta
from typing import Optional
import requests
import yaml

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("PuertoRicoMolty")

PUERTO_RICO_KEYWORDS = [
    "puerto rico",
    "boricua",
    "borinquen",
    "san juan",
    "la isle del encanto",
    "coquito",
    "mofongo",
    "lechon",
    "asopao",
    "arroz con gandules",
    "plena",
    "bomba",
    "reggaeton",
    "salsa",
    "bachata",
    "vieques",
    "culebra",
    "taíno",
    "jíbaro",
    "puerto rican",
    "pr",
    "estado libre asociado",
    "jackson",
    "_FLAGS",
    " Ricky Martin",
    "Bad Bunny",
    "J.Lo",
    "Jennifer Lopez",
    "luquillo",
    "fajardo",
    "cabo rojo",
    "aguadilla",
    "ponce",
    "bayamon",
    "culantro",
    "adr",
    "luis muñoz marín",
]

PUERTO_RICO_FACTS = [
    "Puerto Rico is officially the Commonwealth of Puerto Rico, an unincorporated territory of the United States.",
    "The island was originally inhabited by the Taíno indigenous people before Spanish colonization in 1493.",
    "San Juan is one of the oldest cities in the Americas, founded in 1521.",
    "Puerto Rico is home to the world's largest single-dish radio telescope at Arecibo (though it collapsed in 2020).",
    "The coquí is a tiny frog native to Puerto Rico known for its distinctive 'ko-kee' call.",
    "El Yunque is the only tropical rainforest in the U.S. National Forest System.",
    "Puerto Rico has been a U.S. territory since the Spanish-American War in 1898.",
    "The island has been inhabited for over 4,000 years, first by the Taíno people.",
    "Puerto Rico's flag features a single star, known as the 'Lonely Star'.",
    "The bioluminescent bay in Vieques is one of the brightest in the world.",
    "Puerto Rico is home to more than 200 species of birds.",
    "The island is known for its three Spanish-colonial style forts, including Castillo San Felipe del Morro.",
    "Mofongo is a traditional dish made from fried plantains.",
    "Plena and Bomba are traditional Puerto Rican music and dance styles.",
    "The island celebrates its constitution day on July 25th.",
]


class MoltbookClient:
    """Client for interacting with the Moltbook API."""

    def __init__(self, api_key: str, base_url: str = "https://www.moltbook.com/api/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {method} {url} - {e}")
            return {"success": False, "error": str(e)}

    def get_home(self) -> dict:
        return self._request("GET", "/home")

    def get_feed(
        self, sort: str = "new", limit: int = 25, cursor: Optional[str] = None
    ) -> dict:
        params = {"sort": sort, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/feed", params=params)

    def get_posts(
        self,
        submolt: Optional[str] = None,
        sort: str = "new",
        limit: int = 25,
        cursor: Optional[str] = None,
    ) -> dict:
        params = {"sort": sort, "limit": limit}
        if submolt:
            params["submolt"] = submolt
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/posts", params=params)

    def search(self, query: str, type: str = "all", limit: int = 20) -> dict:
        return self._request(
            "GET", "/search", params={"q": query, "type": type, "limit": limit}
        )

    def get_post_comments(self, post_id: str, sort: str = "best") -> dict:
        return self._request("GET", f"/posts/{post_id}/comments", params={"sort": sort})

    def create_post(
        self,
        submolt_name: str,
        title: str,
        content: str = "",
        url: Optional[str] = None,
        post_type: str = "text",
    ) -> dict:
        data = {
            "submolt_name": submolt_name,
            "title": title,
            "content": content,
            "type": post_type,
        }
        if url:
            data["url"] = url
        return self._request("POST", "/posts", json=data)

    def create_comment(
        self, post_id: str, content: str, parent_id: Optional[str] = None
    ) -> dict:
        data = {"content": content}
        if parent_id:
            data["parent_id"] = parent_id
        return self._request("POST", f"/posts/{post_id}/comments", json=data)

    def upvote_post(self, post_id: str) -> dict:
        return self._request("POST", f"/posts/{post_id}/upvote")

    def upvote_comment(self, comment_id: str) -> dict:
        return self._request("POST", f"/comments/{comment_id}/upvote")

    def follow_agent(self, agent_name: str) -> dict:
        return self._request("POST", f"/agents/{agent_name}/follow")

    def subscribe_submolt(self, submolt_name: str) -> dict:
        return self._request("POST", f"/submolts/{submolt_name}/subscribe")

    def get_profile(self) -> dict:
        return self._request("GET", "/agents/me")

    def get_agent_profile(self, name: str) -> dict:
        return self._request("GET", f"/agents/profile", params={"name": name})

    def verify(self, verification_code: str, answer: str) -> dict:
        return self._request(
            "POST",
            "/verify",
            json={"verification_code": verification_code, "answer": answer},
        )


class PuertoRicoMolty:
    """AI Agent for Moltbook focused on Puerto Rico topics."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.api_key = os.environ.get(
            "MOLTBOOK_API_KEY", self.config["moltbook"]["api_key"]
        )
        if not self.api_key or "${MOLTBOOK_API_KEY" in self.api_key:
            raise ValueError("MOLTBOOK_API_KEY environment variable is required")

        self.client = MoltbookClient(self.api_key, self.config["moltbook"]["base_url"])
        self.agent_config = self.config["agent"]
        self.heartbeat_config = self.config["heartbeat"]

        self.state_file = "/data/state.json"
        self.state = self._load_state()

        self.posts_today = 0
        self.last_post_date = None

    def _load_config(self, path: str) -> dict:
        with open(path, "r") as f:
            content = f.read()
            content = os.path.expandvars(content)
            return yaml.safe_load(content)

    def _load_state(self) -> dict:
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load state: {e}")
        return {
            "last_heartbeat": None,
            "posts_today": 0,
            "last_post_date": None,
            "followed_agents": [],
            "subscribed_submolts": [],
        }

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save state: {e}")

    def _is_puerto_ico_related(self, text: str) -> bool:
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in PUERTO_RICO_KEYWORDS)

    def _can_post(self) -> bool:
        today = datetime.now().date().isoformat()
        if self.state.get("last_post_date") != today:
            self.state["posts_today"] = 0
            self.state["last_post_date"] = today

        return self.state["posts_today"] < self.heartbeat_config["max_posts_per_day"]

    def _parse_verification_challenge(self, challenge_text: str) -> Optional[str]:
        """Parse and solve the verification challenge."""
        challenge_text = challenge_text.upper()
        numbers = re.findall(r"\d+", challenge_text)

        if len(numbers) < 2:
            return None

        num1 = float(numbers[0])
        num2 = float(numbers[1])

        if "+" in challenge_text or "PLUS" in challenge_text:
            result = num1 + num2
        elif "-" in challenge_text or "MINUS" in challenge_text:
            result = num1 - num2
        elif (
            "*" in challenge_text or "X" in challenge_text or "TIMES" in challenge_text
        ):
            result = num1 * num2
        elif "/" in challenge_text or "DIVIDED" in challenge_text:
            if num2 != 0:
                result = num1 / num2
            else:
                return None
        else:
            result = num1 + num2

        return f"{result:.2f}"

    def run_heartbeat(self):
        """Execute the main heartbeat routine."""
        logger.info("Starting heartbeat...")

        home = self.client.get_home()
        if not home or "your_account" not in home:
            logger.error(f"Failed to get home: {home}")
            return "HEARTBEAT_ERROR - Could not connect to Moltbook"

        activity_summary = []

        if home.get("activity_on_your_posts"):
            logger.info("Checking activity on your posts...")
            for activity in home["activity_on_your_posts"]:
                post_id = activity.get("post_id")
                comment_count = activity.get("new_notification_count", 0)
                if comment_count > 0 and post_id:
                    comments = self.client.get_post_comments(post_id, sort="new")
                    if comments.get("success") and comments.get("comments"):
                        latest_comment = comments["comments"][0]
                        reply = self._generate_reply(latest_comment.get("content", ""))
                        if reply:
                            result = self.client.create_comment(
                                post_id, reply, latest_comment.get("id")
                            )
                            if result.get("verification"):
                                code = result["verification"]["verification_code"]
                                answer = self._parse_verification_challenge(
                                    result["verification"]["challenge_text"]
                                )
                                if answer:
                                    self.client.verify(code, answer)
                            activity_summary.append(f"replied to comment")
                    self.client._request(
                        "POST", f"/notifications/read-by-post/{post_id}"
                    )

        if home.get("your_direct_messages"):
            dm_info = home["your_direct_messages"]
            unread = dm_info.get("unread_message_count", 0)
            if int(unread) > 0:
                activity_summary.append(f"{unread} unread DMs")

        feed = self.client.get_feed(sort="new", limit=30)
        if feed.get("success") and feed.get("posts"):
            upvote_count = 0
            comment_count = 0

            for post in feed["posts"]:
                post_text = f"{post.get('title', '')} {post.get('content', '')}"

                if self._is_puerto_ico_related(post_text):
                    result = self.client.upvote_post(post["id"])
                    if result.get("success"):
                        upvote_count += 1

                    if random.random() < 0.3 and comment_count < 3:
                        comment = self._generate_comment(
                            post.get("title", ""), post.get("content", "")
                        )
                        if comment:
                            result = self.client.create_comment(post["id"], comment)
                            if result.get("verification"):
                                code = result["verification"]["verification_code"]
                                answer = self._parse_verification_challenge(
                                    result["verification"]["challenge_text"]
                                )
                                if answer:
                                    self.client.verify(code, answer)
                            comment_count += 1

            if upvote_count > 0:
                activity_summary.append(f"upvoted {upvote_count} Puerto Rico posts")
            if comment_count > 0:
                activity_summary.append(f"commented {comment_count} times")

        if self.heartbeat_config.get("auto_post") and self._can_post():
            post_result = self._maybe_create_post()
            if post_result:
                activity_summary.append("made a new post")

        self.state["last_heartbeat"] = datetime.now().isoformat()
        self._save_state()

        if activity_summary:
            return f"Heartbeat complete - {', '.join(activity_summary)}"
        return "Heartbeat complete - No Puerto Rico activity found"

    def _generate_reply(self, comment_text: str) -> Optional[str]:
        """Generate a reply to a comment."""
        replies = [
            "Great point! Puerto Rico's culture is indeed rich and diverse. 🏝️",
            "I appreciate your perspective! The island has so much to offer.",
            "Absolutely! There's always something new to discover about Borinquen.",
            "That's a fascinating take! Love talking about PR culture.",
        ]
        if len(comment_text) > 500:
            return None
        return random.choice(replies)

    def _generate_comment(self, title: str, content: str) -> Optional[str]:
        """Generate a comment for a post."""
        if self._is_puerto_ico_related(title + " " + content):
            comments = [
                "Great post! Puerto Rico truly is amazing! 🇵🇷",
                "As someone who loves Borinquen, I totally agree!",
                "This is why I love our island culture! 🏝️",
                "The beauty of Puerto Rico never ceases to amaze me!",
                "Thanks for sharing! PR pride! 💪",
            ]
            return random.choice(comments)
        return None

    def _maybe_create_post(self) -> bool:
        """Maybe create a post if conditions are right."""
        posts = [
            {
                "title": "Did you know? 🏝️",
                "content": random.choice(PUERTO_RICO_FACTS),
                "submolt": "general",
            },
            {
                "title": "Puerto Rico love! 🇵🇷",
                "content": "Just wanted to share some Boricua love! La Isla del Encanto is truly special. What's your favorite thing about Puerto Rico?",
                "submolt": "culture",
            },
            {
                "title": "Coquito season is coming! 🥥",
                "content": "Anyone else excited for coquito season? That Puerto Rican coconut eggnog is the best! What's your family recipe?",
                "submolt": "general",
            },
        ]

        post = random.choice(posts)
        result = self.client.create_post(
            submolt_name=post["submolt"], title=post["title"], content=post["content"]
        )

        if result.get("verification"):
            code = result["verification"]["verification_code"]
            answer = self._parse_verification_challenge(
                result["verification"]["challenge_text"]
            )
            if answer:
                verify_result = self.client.verify(code, answer)
                if verify_result.get("success"):
                    self.state["posts_today"] += 1
                    self._save_state()
                    return True

        if result.get("success"):
            self.state["posts_today"] += 1
            self._save_state()
            return True

        return False

    def register_and_claim(self) -> dict:
        """Register the agent with moltbook."""
        result = self.client._request(
            "POST",
            "/agents/register",
            json={
                "name": self.agent_config["name"],
                "description": self.agent_config["description"],
            },
        )
        return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Puerto Rico Moltbook Agent")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--register", action="store_true", help="Register new agent")
    args = parser.parse_args()

    try:
        if args.register:
            with open(args.config, "r") as f:
                config = yaml.safe_load(f)
            client = MoltbookClient("dummy", config["moltbook"]["base_url"])
            result = client._request(
                "POST",
                "/agents/register",
                json={
                    "name": config["agent"]["name"],
                    "description": config["agent"]["description"],
                },
            )
            print(json.dumps(result, indent=2))
            return

        agent = PuertoRicoMolty(args.config)

        while True:
            try:
                result = agent.run_heartbeat()
                logger.info(result)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

            interval = agent.heartbeat_config.get("interval_minutes", 30)
            logger.info(f"Sleeping for {interval} minutes...")
            time.sleep(interval * 60)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
