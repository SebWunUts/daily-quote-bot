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
        # Create hash based on title and first paragraph of content
        quote_identifier = f"{quote_data['title']}|{quote_data['content'][:200]}"
        return hashlib.md5(quote_identifier.encode()).hexdigest()

    def load_last_quote_data(self):
        """Load the last sent quote data"""
        try:
            if os.path.exists(self.quote_tracking_file):
                with open(self.quote_tracking_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
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
                'fetch_date': quote_data['fetch_date']
            }
            with open(self.quote_tracking_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2)
            logger.info("Quote data saved successfully")
        except Exception as e:
            logger.error(f"Could not save quote data: {e}")

    def is_new_quote(self, current_quote_data):
        """Check if we should send today's quote (only once per day)"""
        current_hash = self.get_quote_hash(current_quote_data)
        last_data = self.load_last_quote_data()
        
        # Get today's date
        today = str(date.today())
        
        if not last_data:
            logger.info("No previous quote data found - sending today's quote")
            return True, current_hash
        
        # Check if we already sent a quote today
        last_sent_date = last_data.get('fetch_date')
        if last_sent_date == today:
            logger.info(f"Already sent a quote today ({today}) - skipping")
            return False, current_hash
        
        # It's a new day, send the quote
        logger.info(f"New day detected! Last sent: {last_sent_date}, Today: {today}")
        return True, current_hash

    def fetch_daily_quote(self):
        """Fetch the daily motivational quote from greatday.com"""
        try:
            url = "https://www.greatday.com/"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0'
            }

            logger.info("Fetching quote from greatday.com...")
            response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            logger.info(f"Response status: {response.status_code}")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            content_text = soup.get_text()
            lines = [line.strip() for line in content_text.split('\n') if line.strip()]

            # Parse the content
            date_str = ""
            title = ""
            content = []
            author = "Ralph Marston"

            # Find date and title
            for i, line in enumerate(lines):
                if any(day in line for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']):
                    date_str = line
                    if i + 1 < len(lines):
                        title = lines[i + 1]
                    break

            # Extract main content with better filtering
            content_started = False
            for line in lines:
                if line == title and title:
                    content_started = True
                    continue
                elif content_started:
                    # Stop when we hit the author line or footer content
                    if line.startswith('Ralph Marston') or line == 'Ralph Marston':
                        # Only set author if we haven't found it yet
                        if author == "Ralph Marston":  # default value
                            author = line
                        break
                    # Stop at common footer/navigation elements
                    elif any(word in line.lower() for word in [
                        'copyright', 'previous', 'permission', 'subscribe', 'email', 
                        'greatday.com', 'make a plan', 'weekly focus', 'archives',
                        'home', 'contact', 'privacy', 'terms'
                    ]):
                        break
                    # Stop if line looks like a title for next article (short, title-case)
                    elif (len(line.split()) <= 4 and 
                          line.istitle() and 
                          not line.endswith('.') and 
                          len(content) > 0):
                        break
                    # Include valid content lines
                    elif (line and 
                          len(line) > 10 and 
                          not line.startswith('http') and
                          not line.startswith('—') and
                          '©' not in line):
                        content.append(line)

            # Clean up content - remove any trailing author references
            cleaned_content = []
            for paragraph in content:
                # Skip paragraphs that are just author names or short phrases
                if (paragraph.strip() != 'Ralph Marston' and 
                    not paragraph.strip().startswith('— Ralph') and
                    len(paragraph.strip()) > 15):
                    cleaned_content.append(paragraph)

            # Fallback if no content found
            if not date_str:
                date_str = datetime.now().strftime("%A, %B %d, %Y")
            if not title:
                title = "Daily Motivation"
            if not cleaned_content:
                cleaned_content = ["Stay positive and keep moving forward. Every day is a new opportunity to grow and improve."]

            quote_data = {
                'date': date_str,
                'title': title,
                'content': '\n\n'.join(cleaned_content),
                'author': author,
                'fetch_date': str(date.today())
            }

            logger.info(f"Successfully fetched quote: {title}")
            logger.info(f"Content paragraphs: {len(cleaned_content)}")
            return quote_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching quote: {e}")
            return self.get_fallback_quote()
        except Exception as e:
            logger.error(f"Error fetching quote: {e}")
            return self.get_fallback_quote()

    def get_fallback_quote(self):
        """Return a fallback motivational quote if website is unavailable"""
        fallback_quotes = [
            {
                'title': 'Persistence Pays',
                'content': 'Success is not final, failure is not fatal: it is the courage to continue that counts. Keep pushing forward, even when the path seems difficult.',
                'author': 'Daily Motivator'
            },
            {
                'title': 'New Beginnings',
                'content': 'Every day is a fresh start. Yesterday\'s mistakes don\'t define today\'s possibilities. Embrace the opportunity to grow and improve.',
                'author': 'Daily Motivator'
            },
            {
                'title': 'Inner Strength',
                'content': 'You are stronger than you think and more capable than you realize. Trust in your abilities and take confident steps toward your goals.',
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
            
            data = {
                'chat_id': str(self.chat_id),
                'text': message[:4000],  # Telegram message limit
                'parse_mode': 'HTML'  # Enable HTML formatting
            }

            logger.info(f"Sending message to Telegram (length: {len(message)})")
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

        # Fetch quote
        quote_data = self.fetch_daily_quote()
        
        if not quote_data:
            error_msg = "❌ Sorry, couldn't fetch today's quote. Please try again later."
            self.send_to_telegram(error_msg)
            return "Failed to fetch quote"

        # Check if this is a new quote
        is_new, current_hash = self.is_new_quote(quote_data)
        
        if not is_new:
            logger.info("📋 No new quote available - skipping send")
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
