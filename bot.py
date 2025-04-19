import os
import json
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from telegram.error import TimedOut, NetworkError
from supabase import create_client, Client
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# Логирование переменных для отладки
print(f"BOT_TOKEN: {BOT_TOKEN}")
print(f"SUPABASE_URL: {SUPABASE_URL}")
print(f"SUPABASE_KEY: {SUPABASE_KEY}")
print(f"ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")

# Проверка, что все переменные окружения загружены
if not all([BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY, ADMIN_CHAT_ID]):
    raise ValueError("Одна или несколько переменных окружения не заданы. Проверьте файл .env.")

# Инициализация Supabase
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Ошибка инициализации Supabase: {e}")
    raise

# Список продуктов (аналогичный сайту)
PRODUCTS = [
    {"id": 1, "name": "Uludağ Premium Sparkling 250 мл", "price": 14900, "description": "Освежающая газированная вода для блюд."},
    {"id": 2, "name": "Uludağ Premium Sparkling 750 мл", "price": 27300, "description": "Идеально для больших мероприятий."},
    {"id": 3, "name": "Uludağ Premium Still 350 мл", "price": 12550, "description": "Мягкая вода для вин и десертов."},
    {"id": 4, "name": "Uludağ Premium Still 750 мл", "price": 23500, "description": "Премиальная негазированная вода."},
    {"id": 5, "name": "Uludağ Premium 1 литр", "price": 19500, "description": "Универсальная вода для любых целей."},
    {"id": 6, "name": "Uludağ Classic 250 мл", "price": 8000, "description": "Классический вкус Uludağ."},
    {"id": 7, "name": "Uludağ Special Edition 250 мл", "price": 9500, "description": "Эксклюзивная версия для особых случаев."},
]

def start(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /start."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"

    # Проверка согласия пользователя
    if not context.user_data.get("agreed", False):
        keyboard = [
            [InlineKeyboardButton("Я согласен", callback_data="agree")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "Добро пожаловать в Uludağ Market Bot! 🥤\n\n"
            "ООО 'Serrada Uludağ Uzbekistan' предлагает продукцию Uludağ. "
            "Продолжая, вы соглашаетесь с условиями публичной оферты.",
            reply_markup=reply_markup
        )
    else:
        show_catalog(update, context)

def button_callback(update: Update, context: CallbackContext) -> None:
    """Обработчик нажатий на кнопки."""
    query = update.callback_query
    query.answer()

    user_id = query.from_user.id
    username = query.from_user.username or "Unknown"

    if query.data == "agree":
        context.user_data["agreed"] = True
        query.message.delete()
        show_catalog(update, context)
    elif query.data == "show_cart":
        show_cart(update, context)
    elif query.data == "checkout":
        checkout(update, context)
    elif query.data == "catalog":
        show_catalog(update, context)
    elif query.data == "clear_cart":
        context.user_data["cart"] = []
        query.message.reply_text("Корзина очищена! 🗑️")
        show_catalog(update, context)
    elif query.data.startswith("add_"):
        product_id = int(query.data.split("_")[1])
        context.user_data["selected_product"] = product_id
        show_quantity_selector(update, context)
    elif query.data.startswith("quantity_"):
        _, product_id, quantity = query.data.split("_")
        product_id = int(product_id)
        quantity = int(quantity)
        add_to_cart(update, context, product_id, quantity)

def show_catalog(update: Update, context: CallbackContext) -> None:
    """Показывает каталог продуктов."""
    keyboard = []
    for product in PRODUCTS:
        keyboard.append([
            InlineKeyboardButton(
                f"{product['name']} - {product['price']} UZS",
                callback_data=f"add_{product['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton("Посмотреть корзину 🛒", callback_data="show_cart")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = "Добро пожаловать в Uludağ Market! 🥤\nВыберите продукт для добавления в корзину:"
    if update.callback_query:
        update.callback_query.message.reply_text(message, reply_markup=reply_markup)
    else:
        update.message.reply_text(message, reply_markup=reply_markup)

def show_quantity_selector(update: Update, context: CallbackContext) -> None:
    """Показывает выбор количества товара."""
    product_id = context.user_data.get("selected_product")
    if not product_id:
        update.callback_query.message.reply_text("Ошибка: продукт не выбран.")
        return

    product = next((p for p in PRODUCTS if p["id"] == product_id), None)
    if not product:
        update.callback_query.message.reply_text("Ошибка: продукт не найден.")
        return

    keyboard = [
        [
            InlineKeyboardButton("1", callback_data=f"quantity_{product_id}_1"),
            InlineKeyboardButton("2", callback_data=f"quantity_{product_id}_2"),
            InlineKeyboardButton("5", callback_data=f"quantity_{product_id}_5"),
        ],
        [InlineKeyboardButton("Вернуться к каталогу 🔙", callback_data="catalog")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.callback_query.message.reply_text(
        f"Вы выбрали: {product['name']}\nЦена: {product['price']} UZS\n\nВыберите количество:",
        reply_markup=reply_markup
    )

def add_to_cart(update: Update, context: CallbackContext, product_id: int, quantity: int) -> None:
    """Добавляет продукт в корзину с указанным количеством."""
    if "cart" not in context.user_data:
        context.user_data["cart"] = []
    product = next((p for p in PRODUCTS if p["id"] == product_id), None)
    if not product:
        update.callback_query.message.reply_text("Ошибка: продукт не найден.")
        return

    # Проверяем,есть ли уже этот продукт в корзине
    for item in context.user_data["cart"]:
        if item["id"] == product_id:
            item["quantity"] += quantity
            break
    else:
        # Если продукта нет в корзине, добавляем новый
        context.user_data["cart"].append({
            "id": product_id,
            "name": product["name"],
            "price": product["price"],
            "quantity": quantity
        })
    update.callback_query.message.reply_text(f"Добавлено в корзину: {product['name']} ({quantity} шт.)")

def show_cart(update: Update, context: CallbackContext) -> None:
    """Показывает содержимое корзины."""
    if "cart" not in context.user_data or not context.user_data["cart"]:
        update.callback_query.message.reply_text("Ваша корзина пуста. 🛒")
        return

    cart = context.user_data["cart"]
    total = sum(item["price"] * item["quantity"] for item in cart)
    message = "🛒 Ваша корзина:\n\n"
    for item in cart:
        message += f"- {item['name']} ({item['quantity']} шт.) - {item['price'] * item['quantity']} UZS\n"
    message += f"\nИтого: {total} UZS"

    keyboard = [
        [InlineKeyboardButton("Оформить заказ ✅", callback_data="checkout")],
        [InlineKeyboardButton("Очистить корзину 🗑️", callback_data="clear_cart")],
        [InlineKeyboardButton("Вернуться к каталогу 🔙", callback_data="catalog")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.callback_query.message.reply_text(message, reply_markup=reply_markup)

def checkout(update: Update, context: CallbackContext) -> None:
    """Оформляет заказ и отправляет уведомление админу."""
    user_id = update.callback_query.from_user.id
    username = update.callback_query.from_user.username or "Unknown"
    cart = context.user_data.get("cart", [])

    if not cart:
        update.callback_query.message.reply_text("Ваша корзина пуста. 🛒")
        return

    # Сохранение заказа в Supabase
    order_data = {
        "user_id": user_id,
        "username": username,
        "cart": cart,
    }
    try:
        response = supabase.table("orders").insert(order_data).execute()
        print(f"Supabase response: {response}")
    except Exception as e:
        print(f"Error saving to Supabase: {e}")
        update.callback_query.message.reply_text("Произошла ошибка при оформлении заказа. Попробуйте снова.")
        return

    # Отправка уведомления админу с повторными попытками
    total = sum(item["price"] * item["quantity"] for item in cart)
    message = f"🔔 Новый заказ от @{username} (ID: {user_id}):\n\n"
    for item in cart:
        message += f"- {item['name']} ({item['quantity']} шт.) - {item['price'] * item['quantity']} UZS\n"
    message += f"\nИтого: {total} UZS"

    for attempt in range(3):  # Пробуем 3 раза
        try:
            context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
            break
        except (TimedOut, NetworkError) as e:
            print(f"Error sending message to admin (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(2)  # Пауза перед повторной попыткой
            else:
                update.callback_query.message.reply_text("Заказ оформлен, но не удалось уведомить админа.")
                print("Failed to notify admin after 3 attempts.")

    # Очистка корзины
    context.user_data["cart"] = []
    update.callback_query.message.reply_text("Заказ успешно оформлен! Спасибо за покупку! 🎉")

def main() -> None:
    """Запускает бота."""
    # Создание Updater с увеличенным таймаутом
    updater = Updater(BOT_TOKEN, use_context=True, request_kwargs={'read_timeout': 10, 'connect_timeout': 10})

    # Получение диспетчера для регистрации обработчиков
    dp = updater.dispatcher

    # Добавление обработчиков
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_callback))

    # Запуск бота
    print("Bot is running...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()