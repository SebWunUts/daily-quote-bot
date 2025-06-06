#!/usr/bin/env python3
"""
Daily Quote Bot for GitHub Actions
Fetches daily quotes from greatday.com and sends to Telegram
"""

import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime, date
import logging
import sys

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

            # Extract main content
            content_started = False
            for line in lines:
                if line == title and title:
                    content_started = True
                    continue
                elif content_started:
                    if line.startswith('Ralph Marston'):
                        author = line
                        break
                    elif any(word in line.lower() for word in ['copyright', 'previous', 'permission', 'subscribe', 'email']):
                        break
                    elif line and len(line) > 10 and not line.startswith('http'):
                        content.append(line)

            # Fallback if no content found
            if not date_str:
                date_str = datetime.now().strftime("%A, %B %d, %Y")
            if not title:
                title = "Daily Motivation"
            if not content:
                content = ["Stay positive and keep moving forward. Every day is a new opportunity to grow and improve."]

            quote_data = {
                'date': date_str,
                'title': title,
                'content': '\n\n'.join(content[:3]),  # Limit to first 3 paragraphs
                'author': author,
                'fetch_date': str(date.today())
            }

            logger.info(f"Successfully fetched quote: {title}")
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

        # Format and send message
        message = self.format_message(quote_data)
        
        if self.send_to_telegram(message):
            logger.info("✅ Quote sent successfully!")
            return "Quote sent successfully"
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
