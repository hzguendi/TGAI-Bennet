"""
Snarky Motivator Module for TGAI-Bennet.
Periodically sends snarky, sweary motivational messages to keep you moving.
"""

import random
from datetime import datetime
from typing import Dict, Any, List

from src.modules.base_module import BaseModule, ModuleTrigger, TriggerConfig, ModuleExecutionError
from src.utils.logger import get_logger
from src.utils.telegram_formatter import TelegramFormatter


class SnarkyMotivatorModule(BaseModule):
    """
    Snarky Motivator module that sends periodic motivational messages with attitude.
    
    This module demonstrates:
    - Time-triggered periodic messages
    - Using LLM for creative content generation
    - Sending formatted Telegram messages
    - Customizable schedule and behavior
    """
    
    def __init__(self, bot_instance, config):
        super().__init__(bot_instance, config)
        
        # Module metadata
        self.description = "Sends snarky, sweary motivational messages every few minutes"
        self.author = "TGAI-Bennet"
        self.version = "1.0.0"
        
        # Set as time-based trigger, running every few minutes (configurable)
        self.trigger = TriggerConfig(
            ModuleTrigger.TIME,
            interval=120  # Default: 2 minutes in seconds
        )
        
        # Module state
        self.state = {
            'messages_sent': 0,
            'last_message_time': None,
            'last_message': None
        }
        
        # Make sure we have logger
        self.logger = get_logger(self.__class__.__name__)
        
        # Fallback messages if LLM fails
        self.fallback_messages = [
            # Morning themed
            "It's morning, so why the fuck are you still procrastinating? Your future self wants to punch you right now. Start working!",
            "Oh look, you got out of bed. What a fucking achievement. Now do something that actually matters today, genius.",
            "Morning sunshine! While you're deciding whether to work, your competition is already kicking ass. Move it!",
            
            # Afternoon themed
            "Mid-day slump? Tough shit. The clock doesn't care about your excuses. Neither does your deadline.",
            "Afternoon productivity check: Are you kicking ass or just sitting on it? The day's half gone already, dumbass.",
            "Still haven't started that important thing? For fuck's sake, your afternoon is evaporating while you're doomscrolling.",
            
            # Evening themed
            "Evening's here and what have you accomplished? Jack shit? Thought so. It's not too late to salvage something, move it!",
            "The day's almost over and your to-do list is still full of crap you avoided. Feeling proud of that achievement? Get to work!",
            "Evening regrets start with morning laziness. Don't go to bed thinking 'Fuck, I wasted another day.' Do something NOW.",
            
            # Weekend themed
            "It's the weekend! Know what successful people do on weekends? Not fucking nothing, that's for sure. Get up and move!",
            "'But it's the weekend!' said every mediocre person ever. Your goals don't care what day it is. Your ass shouldn't either.",
            "Weekend relaxation is earned, not given. Have you done shit to deserve it? If not, get moving first.",
            
            # General motivation
            "That motivation you're waiting for? It's not coming. Do it anyway, dumbass.",
            "Your comfort zone is where your dreams go to die. Get the fuck out of there and do something scary today.",
            "Remember: you can't spell 'success' without 'u', dumbass. And you can't achieve it without doing the fucking work.",
            "Stop waiting for inspiration to hit you like a magical shit fairy. Inspiration comes AFTER you start working.",
            "That thing you're avoiding? It's still fucking there. And it'll still be there tomorrow, only bigger and uglier.",
            "Do you want to be the person who almost did something great? No? Then stop almost doing it and actually fucking do it!",
            "I'd tell you to reach for the stars, but first maybe just get off your ass and reach for your goals?"
        ]
    
    async def initialize(self) -> None:
        """Initialize the snarky motivator module."""
        self.log_info("Initializing Snarky Motivator Module")
        
        # Load configuration
        interval_minutes = self.get_config('interval_minutes', 600)
        self.trigger.interval = interval_minutes * 60
        
        # Log configuration
        self.log_info(f"Module will send messages every {interval_minutes} minutes")
    
    async def run(self) -> None:
        """Main execution method that runs periodically."""
        self.log_info("Running snarky motivator")
        
        try:
            # Generate the motivational message
            message = await self._generate_motivational_message()
            
            # Send the message
            if await self.send_telegram_message(message):
                # Update state
                self.state['messages_sent'] += 1
                self.state['last_message_time'] = datetime.now().isoformat()
                self.state['last_message'] = message
                
                self.log_info(f"Sent motivational message #{self.state['messages_sent']}")
            else:
                self.log_error("Failed to send motivational message")
            
        except Exception as e:
            self.log_error(f"Error in snarky motivator module: {str(e)}", e)
    
    async def cleanup(self) -> None:
        """Clean up resources used by the module."""
        self.log_info("Cleaning up Snarky Motivator Module")
        # No specific cleanup needed for this module
    
    async def _generate_motivational_message(self) -> str:
        """
        Generate a snarky motivational message using LLM or fallback.
        
        Returns:
            str: Formatted motivational message
        """
        try:
            # Create a prompt for the LLM - Enhanced with more context for variety and uncensored language
            system_message = (
                "You are a snarky, no-nonsense motivational coach with a colorful vocabulary. "
                "You're encouraging but with attitude. You use explicit profanity for emphasis - use actual words like 'fuck', 'shit', 'ass' "
                "without censoring or using asterisks. Never censor your language - use the actual words. "
                "You're not mean-spirited but you don't sugarcoat things. "
                "Your goal is to motivate people to take action and stop procrastinating. "
                "Create varied messages with different tones and approaches each time. "
                "Sometimes focus on goals, sometimes on fears, sometimes on potential - be unpredictable. "
                "Use plenty of colorful analogies and metaphors. Be memorable and don't hold back on the language."
                "You can use quotes from time to time also"
                "Be as random, funny, unexpected and creative as possible to avoid being repetitive."
            )
            
            # Tailor prompt based on time of day and previous messages
            time_of_day = datetime.now().hour
            message_count = self.state.get('messages_sent', 0)
            
            # Add more context for personalization
            time_context = "morning" if 5 <= time_of_day < 12 else "afternoon" if 12 <= time_of_day < 18 else "evening"
            day_of_week = datetime.now().strftime("%A")
            
            # Check if it's a weekend
            is_weekend = day_of_week in ["Saturday", "Sunday"]
            weekend_context = "weekend" if is_weekend else "workday"
            
            prompt = (
                f"Create a short, fun, snarky, motivational message with explicit profanity (use actual words like 'fuck', 'shit', 'ass' - "
                f"DO NOT censor with asterisks) to motivate someone to be productive. "
                f"It's currently {time_context} on a {day_of_week} ({weekend_context}). "
                f"This is message #{message_count + 1} they're receiving today. "
                f"Keep it under 100 words, make it punchy, funny and memorable. "
                f"Include a specific call to action that encourages productivity or self-improvement. "
                f"Base your message on one of these themes: missed opportunities, future regrets, competition, "
                f"self-respect, or the satisfaction of achievement. Choose a different theme than your previous messages. "
                f"MOST IMPORTANT: Ensure you use UNCENSORED profanity - write 'fuck' not 'f*ck', 'ass' not 'a**', 'shit' not 'sh*t' - "
                f"no censorship or asterisks in your language at all."
                f"MOST IMPORTANT: you are not obligated to use all the context (time, day, message count...) use a random combination on none or all randomly to be more unpredictable"
                f"MOST IMPORTANT: just give the message, no quotes, no theme just the message itself"
            )
            
            self.log_info(f"Using direct OpenAI call with model={self.config.get('llm.default_model')}")
            
            # Use the dedicated method for OpenAI format with chat history
            llm_response = await self.generate_llm_response(
                prompt=prompt,
                system_message=system_message,
                chat_id=self.bot.admin_chat_id,  # Use admin chat ID for messages
                use_history=True                 # Leverage conversation history
            )
            
            self.log_info(f"LLM response received. Length: {len(llm_response or '')}")
            
            # Check if we got a valid response
            if not llm_response or len(llm_response.strip()) < 10:
                self.log_warning("LLM returned empty or too short response, using fallback")
                raise ValueError("Empty or insufficient LLM response")
            
            # Format the response for Telegram
            icons = ["🔥", "💪", "⚡", "👊", "🚀", "💯", "⏰", "🎯"]
            icon = random.choice(icons)
            title = f"Motivational Kick in the Ass"
            
            # Use the standard format_telegram_response which now uses minimal escaping
            return self.format_telegram_response(
                title=title,
                content=llm_response,
                status='info'
            )
            
        except Exception as e:
            # Fallback to pre-defined message if LLM fails
            self.log_error(f"LLM generation failed: {str(e)}", e)
            self.log_info("Using fallback message instead")
            
            # Select appropriate fallback message based on time of day and week
            time_of_day = datetime.now().hour
            day_of_week = datetime.now().strftime("%A")
            is_weekend = day_of_week in ["Saturday", "Sunday"]
            
            # Group messages by type
            morning_messages = self.fallback_messages[0:3]
            afternoon_messages = self.fallback_messages[3:6]
            evening_messages = self.fallback_messages[6:9]
            weekend_messages = self.fallback_messages[9:12]
            general_messages = self.fallback_messages[12:]
            
            # Select from appropriate category with higher probability,
            # but still allow some general messages
            if is_weekend:
                # Weekend - 60% weekend, 40% general
                if random.random() < 0.6:
                    message = random.choice(weekend_messages)
                else:
                    message = random.choice(general_messages)
            elif 5 <= time_of_day < 12:
                # Morning - 60% morning, 40% general
                if random.random() < 0.6:
                    message = random.choice(morning_messages)
                else:
                    message = random.choice(general_messages)
            elif 12 <= time_of_day < 18:
                # Afternoon - 60% afternoon, 40% general
                if random.random() < 0.6:
                    message = random.choice(afternoon_messages)
                else:
                    message = random.choice(general_messages)
            else:
                # Evening - 60% evening, 40% general
                if random.random() < 0.6:
                    message = random.choice(evening_messages)
                else:
                    message = random.choice(general_messages)
            
            # Log what type of message we selected
            self.log_info(f"Selected a fallback message for {time_context} on a {weekend_context}")
            
            # Set a dynamic title based on time of day
            icons = ["🔥", "💪", "⚡", "👊", "🚀", "💯", "⏰", "🎯"]
            icon = random.choice(icons)
            
            if is_weekend:
                title = f"Weekend Motivation!"
            elif 5 <= time_of_day < 12:
                title = f"Morning Kick in the Ass!"
            elif 12 <= time_of_day < 18:
                title = f"Afternoon Wake-up Call!"
            else:
                title = f"Evening Push!"
            
            # Use the standard format_telegram_response which now uses minimal escaping
            return self.format_telegram_response(
                title=title,
                content=message,
                status='info'
            )
    
    async def save_state(self) -> Dict[str, Any]:
        """Save the current state of the module."""
        return self.state
    
    async def load_state(self, state: Dict[str, Any]) -> None:
        """Load a previously saved state."""
        self.state = state
