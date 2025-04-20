"""
Gaming News Module for TGAI-Bennet.
Periodically sends updates about gaming news and events.
"""

import random
from datetime import datetime
from typing import Dict, Any, List

from src.modules.base_module import BaseModule, ModuleTrigger, TriggerConfig, ModuleExecutionError
from src.utils.logger import get_logger
from src.utils.telegram_formatter import TelegramFormatter


class GamingNewsModule(BaseModule):
    """
    Gaming News module that sends periodic updates and commentary on gaming events.
    
    This module demonstrates:
    - Time-triggered periodic messages
    - Using LLM for creative content generation with chat history
    - Sending formatted Telegram messages
    """
    
    def __init__(self, bot_instance, config):
        super().__init__(bot_instance, config)
        
        # Module metadata
        self.description = "Sends fun comments and updates about gaming events every two hours"
        self.author = "TGAI-Bennet"
        self.version = "1.0.0"
        
        # Set as time-based trigger, running every two hours (configurable)
        self.trigger = TriggerConfig(
            ModuleTrigger.TIME,
            interval=7200  # Default: 2 hours in seconds
        )
        
        # Module state
        self.state = {
            'messages_sent': 0,
            'last_message_time': None,
            'last_message': None,
            'covered_topics': []
        }
        
        # Ensure we have logger
        self.logger = get_logger(self.__class__.__name__)
        
        # Gaming topics for prompts
        self.gaming_topics = [
            # Game genres
            "open-world RPGs", "first-person shooters", "battle royale games", 
            "MOBA games", "indie games", "action-adventure games", "simulation games",
            "roguelike games", "survival games", "strategy games", "MMORPGs",
            
            # Popular franchises
            "The Elder Scrolls", "Call of Duty", "FIFA", "Grand Theft Auto", 
            "Legend of Zelda", "Minecraft", "Fortnite", "League of Legends",
            "World of Warcraft", "Assassin's Creed", "Overwatch", "Cyberpunk",
            "Elden Ring", "God of War", "Horizon", "Halo", "Final Fantasy",
            
            # Gaming platforms
            "PC gaming", "PlayStation", "Xbox", "Nintendo Switch", "mobile gaming",
            "cloud gaming", "VR gaming", "AR gaming",
            
            # Industry topics
            "game developers", "gaming monetization", "loot boxes", "esports",
            "game streaming", "speedrunning", "gaming controversies", "game modding",
            "gaming communities", "early access games", "indie development",
            "gaming conventions", "game patches", "gaming hardware",
            
            # Current trends
            "AI in games", "procedural generation", "crossplay", "free-to-play games",
            "game preservation", "gaming subscription services", "retro gaming",
            "game remakes and remasters", "gaming accessibility", "games as a service"
        ]
    
    async def initialize(self) -> None:
        """Initialize the gaming news module."""
        self.log_info("Initializing Gaming News Module")
        
        # Load configuration
        interval_minutes = self.get_config('interval_minutes', 120)
        self.trigger.interval = interval_minutes * 60
        
        # Log configuration
        self.log_info(f"Module will send gaming updates every {interval_minutes} minutes")
    
    async def run(self) -> None:
        """Main execution method that runs periodically."""
        self.log_info("Running gaming news update")
        
        try:
            # Generate the gaming update message
            message = await self._generate_gaming_update()
            
            # Send the message
            if await self.send_telegram_message(message):
                # Update state
                self.state['messages_sent'] += 1
                self.state['last_message_time'] = datetime.now().isoformat()
                self.state['last_message'] = message
                
                self.log_info(f"Sent gaming update #{self.state['messages_sent']}")
            else:
                self.log_error("Failed to send gaming update")
            
        except Exception as e:
            self.log_error(f"Error in gaming news module: {str(e)}", e)
    
    async def cleanup(self) -> None:
        """Clean up resources used by the module."""
        self.log_info("Cleaning up Gaming News Module")
        # No specific cleanup needed for this module
    
    async def _generate_gaming_update(self) -> str:
        """
        Generate a fun gaming news update using LLM.
        
        Returns:
            str: Formatted gaming news message
        """
        try:
            # Select a random gaming topic from our list
            # Avoid using the same topic too frequently
            available_topics = [t for t in self.gaming_topics if t not in self.state.get('covered_topics', [])[-5:]]
            
            if not available_topics:
                available_topics = self.gaming_topics
            
            topic = random.choice(available_topics)
            
            # Track the topic we're covering
            if 'covered_topics' not in self.state:
                self.state['covered_topics'] = []
            self.state['covered_topics'].append(topic)
            
            # Create a prompt for the LLM
            system_message = (
                "You are Bennet, a witty and knowledgeable gaming enthusiast who provides fun, "
                "entertaining commentary on gaming news and trends. Your tone is conversational, "
                "engaging, and slightly irreverent. You use gaming slang naturally and make "
                "references that gamers would appreciate. You're responding in a Telegram chat, "
                "so keep your message concise yet informative."
            )
            
            # Create prompt based on the selected topic
            message_count = self.state.get('messages_sent', 0)
            current_date = datetime.now().strftime("%B %Y")
            
            prompt = (
                f"Create a brief, entertaining gaming update about {topic}. "
                f"Provide some current insights or predictions about this topic as of {current_date}. "
                f"Add in your personal take with a touch of humor and maybe a gaming reference or joke. "
                f"Keep it concise (under 150 words) but packed with personality. "
                f"This is update #{message_count + 1} in the series."
            )
            
            self.log_info(f"Generating gaming update about: {topic}")
            
            # Get LLM response with chat history to maintain consistent style
            llm_response = await self.generate_llm_response(
                prompt=prompt,
                system_message=system_message,
                chat_id=self.bot.admin_chat_id,  # Use admin chat ID for consistent history
                use_history=True,                # Use conversation history for style consistency
                temperature=0.8                  # Slightly higher temperature for creativity
            )
            
            self.log_info(f"LLM response received. Length: {len(llm_response or '')}")
            
            # Check if we got a valid response
            if not llm_response or len(llm_response.strip()) < 10:
                self.log_warning("LLM returned empty or too short response, using fallback")
                raise ValueError("Empty or insufficient LLM response")
            
            # Format the response for Telegram
            icons = ["🎮", "🕹️", "🎯", "🏆", "🎲", "🎪", "👾", "🎭", "🎨", "🎧", "🎤"]
            icon = random.choice(icons)
            title = f"{icon} Gaming Update: {topic.title()}"
            
            # Format telegram response
            return self.format_telegram_response(
                title=title,
                content=llm_response,
                status='info'
            )
            
        except Exception as e:
            self.log_error(f"Gaming update generation failed: {str(e)}", e)
            
            # If LLM fails, create a simple fallback message
            icons = ["🎮", "🕹️", "🎯", "🏆"]
            icon = random.choice(icons)
            title = f"{icon} Gaming Update"
            
            fallback_content = (
                f"It's time for your gaming update! I was going to share some insights about {topic}, "
                f"but my neural networks are taking a quick respawn. Stay tuned for the next update!"
            )
            
            return self.format_telegram_response(
                title=title,
                content=fallback_content,
                status='info'
            )
    
    async def save_state(self) -> Dict[str, Any]:
        """Save the current state of the module."""
        return self.state
    
    async def load_state(self, state: Dict[str, Any]) -> None:
        """Load a previously saved state."""
        self.state = state
