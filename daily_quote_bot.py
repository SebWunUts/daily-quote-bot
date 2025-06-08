#!/usr/bin/env python3
"""
Daily Quote Bot for GitHub Actions
Fetches daily quotes from greatday.com and sends to Telegram
Only sends when there's a new quote available
"""

import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime, date
import logging
import sys
import hashlib
import json
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class DailyQuoteBot:
    def __init__(self, telegram_token, chat_id):
        """Initialize the bot with Telegram credentials"""
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{telegram_token}"
        self.quote_tracking_file = 'last_quote_data.json'

    def get_quote_hash(self, quote_data):
        """Generate a unique hash for the quote to detect changes"""
        # Create hash based on date, title and first 200 chars of content
        quote_identifier = f"{quote_data['date']}|{quote_data['title']}|{quote_data['content'][:200]}"
        return hashlib.md5(quote_identifier.encode()).hexdigest()

    def load_last_quote_data(self):
        """Load the last sent quote data"""
        try:
            if os.path.exists(self.quote_tracking_file):
                with open(self.quote_tracking_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Handle empty or malformed files
                    if not data or not isinstance(data, dict):
                        return None
                    return data
            return None
        except Exception as e:
            logger.warning(f"Could not load last quote data: {e}")
            return None

    def save_quote_data(self, quote_data, quote_hash):
        """Save the current quote data and hash"""
        try:
            data_to_save = {
                'hash': quote_hash,
                'date': quote_data['date'],
                'title': quote_data['title'],
                'sent_at': datetime.now().isoformat(),
                'fetch_date': quote_data['fetch_date'],
                'content_preview': quote_data['content'][:100] + "..." if len(quote_data['content']) > 100 else quote_data['content']
            }
            with open(self.quote_tracking_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            logger.info(f"Quote data saved successfully - Hash: {quote_hash[:8]}...")
        except Exception as e:
            logger.error(f"Could not save quote data: {e}")

    def is_new_quote(self, current_quote_data):
        """Check if this is a new quote we haven't sent before"""
        current_hash = self.get_quote_hash(current_quote_data)
        last_data = self.load_last_quote_data()
        
        logger.info(f"Current quote hash: {current_hash[:8]}...")
        
        if not last_data:
            logger.info("No previous quote data found - this is a new quote")
            return True, current_hash
        
        last_hash = last_data.get('hash', '')
        logger.info(f"Last quote hash: {last_hash[:8]}...")
        
        if current_hash != last_hash:
            logger.info("Quote content has changed - this is a new quote!")
            return True, current_hash
        else:
            logger.info("Quote content is the same as last time - skipping")
            return False, current_hash

    def fetch_daily_quote(self):
        """Fetch the daily motivational quote from greatday.com"""
        try:
            url = "https://www.greatday.com/"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'no-cache'
            }

            logger.info("Fetching quote from greatday.com...")
            
            # Add retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
                    response.raise_for_status()
                    break
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                    else:
                        raise
            
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response size: {len(response.content)} bytes")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Debug: Save first 1000 chars of content for debugging
            content_preview = soup.get_text()[:1000]
            logger.info(f"Content preview: {content_preview[:200]}...")
            
            content_text = soup.get_text()
            lines = [line.strip() for line in content_text.split('\n') if line.strip()]

            # Parse the content
            date_str = ""
            title = ""
            content = []
            author = "Ralph Marston"

            # Find date and title with improved detection
            for i, line in enumerate(lines):
                # Look for day names in the line
                if any(day in line for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']):
                    date_str = line
                    # Look for title in next few lines
                    for j in range(i + 1, min(i + 4, len(lines))):
                        potential_title = lines[j]
                        # Title is usually short and not too long
                        if (len(potential_title) > 5 and 
                            len(potential_title) < 100 and 
                            not any(skip_word in potential_title.lower() for skip_word in 
                                   ['copyright', 'ralph marston', 'greatday', 'http', 'www'])):
                            title = potential_title
                            break
                    break

            # Extract main content with improved filtering
            content_started = False
            title_found = False
            
            for line in lines:
                # Start collecting content after we find the title
                if line == title and title and not title_found:
                    content_started = True
                    title_found = True
                    continue
                elif content_started:
                    # Stop conditions
                    if (line.startswith('Ralph Marston') or 
                        line == 'Ralph Marston' or
                        '— Ralph' in line):
                        if author == "Ralph Marston":
                            author = line
                        break
                    elif any(word in line.lower() for word in [
                        'copyright', 'previous', 'permission', 'subscribe', 'email', 
                        'greatday.com', 'make a plan', 'weekly focus', 'archives',
                        'home', 'contact', 'privacy', 'terms', 'navigate'
                    ]):
                        break
                    # Include valid content lines
                    elif (line and 
                          len(line) > 15 and 
                          not line.startswith('http') and
                          not line.startswith('—') and
                          '©' not in line and
                          not line.isupper() and  # Skip navigation/header text
                          len(line.split()) > 3):  # Ensure it's a proper sentence
                        content.append(line)

            # Fallback parsing if main method didn't work
            if not date_str or not title or not content:
                logger.warning("Primary parsing failed, trying fallback method...")
                
                # Try to find any meaningful content
                all_text = ' '.join(lines)
                
                # Look for patterns that might be the quote
                paragraphs = [p.strip() for p in all_text.split('.') if len(p.strip()) > 50]
                
                if paragraphs:
                    content = [paragraphs[0] + '.']  # Take first substantial paragraph
                
                if not date_str:
                    date_str = datetime.now().strftime("%A, %B %d, %Y")
                if not title:
                    title = "Daily Motivation"

            # Final fallback
            if not content:
                logger.warning("Could not extract content, using fallback")
                return self.get_fallback_quote()

            quote_data = {
                'date': date_str,
                'title': title,
                'content': '\n\n'.join(content),
                'author': author,
                'fetch_date': str(date.today())
            }

            logger.info(f"Successfully parsed quote:")
            logger.info(f"  Date: {date_str}")
            logger.info(f"  Title: {title}")
            logger.info(f"  Content length: {len(quote_data['content'])} chars")
            logger.info(f"  Content paragraphs: {len(content)}")
            
            return quote_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching quote: {e}")
            return self.get_fallback_quote()
        except Exception as e:
            logger.error(f"Error fetching quote: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return self.get_fallback_quote()

    def get_fallback_quote(self):
        """Return a fallback motivational quote if website is unavailable"""
        fallback_quotes = [
            {
                'title': 'Persistence Pays',
                'content': 'Success is not final, failure is not fatal: it is the courage to continue that counts. Keep pushing forward, even when the path seems difficult. Each challenge you overcome makes you stronger and more resilient.',
                'author': 'Daily Motivator'
            },
            {
                'title': 'New Beginnings',
                'content': 'Every day is a fresh start. Yesterday\'s mistakes don\'t define today\'s possibilities. Embrace the opportunity to grow and improve. Your potential is limitless when you approach each day with renewed energy.',
                'author': 'Daily Motivator'
            },
            {
                'title': 'Inner Strength',
                'content': 'You are stronger than you think and more capable than you realize. Trust in your abilities and take confident steps toward your goals. The power to change your life lies within you.',
                'author': 'Daily Motivator'
            },
            {
                'title': 'Focus Forward',
                'content': 'Focus on progress, not perfection. Every small step forward is a victory worth celebrating. Consistency in small actions leads to extraordinary results over time.',
                'author': 'Daily Motivator'
            }
        ]
        
        import random
        selected_quote = random.choice(fallback_quotes)
        
        return {
            'date': datetime.now().strftime("%A, %B %d, %Y"),
            'title': selected_quote['title'],
            'content': selected_quote['content'],
            'author': selected_quote['author'],
            'fetch_date': str(date.today())
        }

    def send_to_telegram(self, message):
        """Send message to Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            
            # Split message if too long
            max_length = 4000
            if len(message) > max_length:
                message = message[:max_length-10] + "...\n\n[Truncated]"
            
            data = {
                'chat_id': str(self.chat_id),
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }

            logger.info(f"Sending message to Telegram (length: {len(message)} chars)")
            response = requests.post(url, data=data, timeout=30)
            
            logger.info(f"Telegram response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    logger.info("✅ Message sent successfully to Telegram")
                    return True
                else:
                    logger.error(f"❌ Telegram API error: {result}")
                    return False
            else:
                logger.error(f"❌ HTTP error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"❌ Error sending to Telegram: {e}")
            return False

    def format_message(self, quote_data):
        """Format the quote message for Telegram"""
        message = f"🌟 <b>Daily Motivator</b>\n\n"
        message += f"📅 <i>{quote_data['date']}</i>\n\n"
        message += f"<b>{quote_data['title']}</b>\n\n"
        message += f"{quote_data['content']}\n\n"
        message += f"— <i>{quote_data['author']}</i>"
        return message

    def run(self):
        """Main function to fetch and send daily quote"""
        logger.info("🚀 Starting daily quote bot...")
        logger.info(f"Current time: {datetime.now().isoformat()}")

        # Fetch quote
        quote_data = self.fetch_daily_quote()
        
        if not quote_data:
            error_msg = "❌ Sorry, couldn't fetch today's quote. Please try again later."
            self.send_to_telegram(error_msg)
            return "Failed to fetch quote"

        # Check if this is a new quote
        is_new, current_hash = self.is_new_quote(quote_data)
        
        if not is_new:
            logger.info("📋 Quote hasn't changed since last check - skipping send")
            return "No new quote - skipped"

        # Format and send message
        message = self.format_message(quote_data)
        
        if self.send_to_telegram(message):
            # Save quote data only after successful send
            self.save_quote_data(quote_data, current_hash)
            logger.info("✅ New quote sent successfully!")
            return "New quote sent successfully"
        else:
            logger.error("❌ Failed to send quote")
            return "Failed to send quote"

def main():
    """Main function - gets credentials from environment variables"""
    
    # Get credentials from environment variables (GitHub secrets)
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

    # Validate credentials
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN environment variable not found")
        logger.error("Please add your bot token to GitHub secrets")
        sys.exit(1)
        
    if not TELEGRAM_CHAT_ID:
        logger.error("❌ TELEGRAM_CHAT_ID environment variable not found")
        logger.error("Please add your chat ID to GitHub secrets")
        sys.exit(1)

    logger.info(f"Bot token: {TELEGRAM_BOT_TOKEN[:10]}...")
    logger.info(f"Chat ID: {TELEGRAM_CHAT_ID}")

    # Create and run bot
    bot = DailyQuoteBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    result = bot.run()
    logger.info(f"Final result: {result}")

if __name__ == "__main__":
    main()
