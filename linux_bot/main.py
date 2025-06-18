import telebot
from telebot import types
import logging
from logging.handlers import TimedRotatingFileHandler
import time
from dotenv import load_dotenv
import os
import subprocess
from glob import glob
import html
import textwrap
import json

# ENV VARIABLES
# Load environment variables from .env
load_dotenv(dotenv_path='../.env')

SECRET_TOKEN = os.environ.get('SECRET_TOKEN')
CHAT_ID_PERSON1 = int(os.environ.get('CHAT_ID_PERSON1'))
ALLOWED_USERS = [CHAT_ID_PERSON1]

wol_address = os.environ.get('WOL_ADDRESS')
wol_hostname = os.environ.get('WOL_HOSTNAME')

# LOGGING
log_directory = './logs/'
log_file_path = os.path.join(log_directory, 'linux_bot.log')
server_states_json = "../linux_monitoring/server_states.json"

# Ensure the log directory exists
os.makedirs(log_directory, exist_ok=True)

# Use TimedRotatingFileHandler to create a new log file every day
handler = TimedRotatingFileHandler(log_file_path, when="midnight", interval=1, backupCount=7)
handler.suffix = "%Y-%m-%d.log"  # Add a suffix with the date format

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# Set the logging level
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Add the handler to the logger
logger.addHandler(handler)

bot = telebot.TeleBot(SECRET_TOKEN, parse_mode="HTML")

# Variables
commands_telegram = """
<b>Menu - Menu of the bot</b>
/menu

<b>Start - Start the bot</b>
/start
"""

# Read service and container lists from files
with open('bot_services.txt', 'r') as services_file:
    services_list = services_file.read().splitlines()

with open('bot_logfiles.txt', 'r') as log_files_file:
    log_files = log_files_file.read().splitlines()
    
with open('bot_servers.txt', 'r') as servers_file:
    servers_list = servers_file.read().splitlines()


@bot.message_handler(commands=['start'], func=lambda message: message.chat.id in ALLOWED_USERS)
def send_start(message):
    logging.info(f"User {message.from_user.first_name} started the bot")
    global commands_telegram
    welcome_message = f"""Hey {message.from_user.first_name}, I'm a Linux Bot.

The most convenient bot for the Raspberry Pi or Linux server you programmed. If you hit /menu you can choose what you want to do. For shortcuts use the commands.

These are the commands I listen to:
{commands_telegram}"""

    bot.send_message(message.chat.id, welcome_message)


# MENUS
@bot.message_handler(commands=['menu'], func=lambda message: message.chat.id in ALLOWED_USERS)
def send_handle_menu(message):
    markup_menu = types.ReplyKeyboardMarkup(
        row_width=4, one_time_keyboard=True)
    # Add buttons
    button_wol = types.InlineKeyboardButton("💻 Wake up WoL")
    button_services = types.InlineKeyboardButton("📦 Services")
    button_docker = types.InlineKeyboardButton("🐳   Docker")
    button_logs = types.InlineKeyboardButton("📜       Logs")
    button_sendcommand = types.InlineKeyboardButton("📤 Send command")
    button_checkservers = types.InlineKeyboardButton("🔔 Check servers")
    button_systeminfo = types.InlineKeyboardButton("📃 System info")
    button_stresstest = types.InlineKeyboardButton("💪 Stress test")
    button_fancontrol = types.InlineKeyboardButton("💨 Fan state")
    button_reboot = types.InlineKeyboardButton("🔁 Reboot")

    markup_menu.add(button_wol, button_services, button_docker, button_logs, button_sendcommand, button_checkservers, button_systeminfo, button_stresstest, button_fancontrol, button_reboot)
    option_selection_text = "Choose one of the following options:"

    bot.send_message(message.chat.id, option_selection_text,
                     reply_markup=markup_menu)


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "🔙 Go back to main")
def handle_go_back(message):
    send_handle_menu(message)
    

# WOL
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "💻 Wake up WoL")
def handle_wakewol_menu(message):
    markup_wakewol = types.ReplyKeyboardMarkup(
        row_width=2, one_time_keyboard=True)
    # Add buttons
    button1 = types.InlineKeyboardButton("💻 Wake up")
    button2 = types.InlineKeyboardButton("❌ Cancel wake up")
    button3 = types.InlineKeyboardButton("🔙 Go back to main")

    markup_wakewol.add(button1, button2, button3)
    option_selection_text = f"Are you sure you want to wake up {wol_hostname}?"

    bot.send_message(message.chat.id, option_selection_text,
                     reply_markup=markup_wakewol)


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "💻 Wake up")
def handle_wakewol_now(message):
    logging.info(f"User {message.from_user.first_name} requested a wake up")
    bot.reply_to(message, f"Waking up {wol_hostname}.")
    command = f"sudo etherwake -i eth0 {wol_address}"
    try:
        logging.info(f"Waking up {wol_hostname}.")
        logging.info(f"Command: {command}")
        subprocess.run(command,
                       shell=True, text=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Waking up failed. Error: {e}")
        print(f"Waking up failed. Error: {e}")
        bot.reply_to(message, f"Waking up failed. Error: {e}")
    
    send_handle_menu(message)


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "❌ Cancel wake up")
def handle_cancel_wakewol(message):
    logging.info(f"User {message.from_user.first_name} canceled the wake up")
    bot.reply_to(message, "Wake up canceled.")
    send_handle_menu(message)


@bot.message_handler(commands=['wakewol'], func=lambda message: message.chat.id in ALLOWED_USERS)
def send_handle_wakewol(message):
    handle_wakewol_menu(message)


# SERVICES
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "📦 Services")
def handle_services_menu(message):
    markup_services_menu = types.ReplyKeyboardMarkup(
        row_width=3, one_time_keyboard=True)
    # Add buttons
    button1 = types.InlineKeyboardButton("🟩 Start a service")
    button2 = types.InlineKeyboardButton("🟨 Restart a service")
    button3 = types.InlineKeyboardButton("🟥 Stop a service")
    button4 = types.InlineKeyboardButton("🟩🟩 Start all services")
    button5 = types.InlineKeyboardButton("🟨🟨 Restart all services")
    button6 = types.InlineKeyboardButton("🟥🟥 Stop all services")
    button7 = types.InlineKeyboardButton("🟫 Get status services")
    button8 = types.InlineKeyboardButton("🔙 Go back to main")

    markup_services_menu.add(button1, button2, button3,
                             button4, button5, button6, button7, button8)
    option_selection_text = "What do you want to do?"

    bot.send_message(message.chat.id, option_selection_text,
                     reply_markup=markup_services_menu)


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text.startswith("🔙 Go back to services"))
def handle_service_go_back(message):
    handle_services_menu(message)


@bot.message_handler(commands=['services'], func=lambda message: message.chat.id in ALLOWED_USERS)
def send_handle_servicescommand(message):
    handle_services_menu(message)


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "🟫 Get status services")
def handle_getstatusservices(message):
    logging.info(f"User {message.from_user.first_name} requested service status")
    service_status_message = "<b>Status services:</b>"

    for service in services_list:
        try:
            service_status = subprocess.run(f'systemctl status {service} | grep "Active:" | awk \'{{print "{service}:", $2, $3}}\'', shell=True, capture_output=True, text=True)
            service_status_message += f"\n{service_status.stdout}"
        except subprocess.CalledProcessError as e:
            logging.error(f"Get status services failed. Error: {e}")
            print(f"Get status services failed. Error: {e}")
            service_status_message += f"\nError: {e}"

    bot.send_message(message.chat.id, service_status_message, parse_mode="HTML")

    # Open service menu
    handle_services_menu(message)

# Start a service
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "🟩 Start a service")
def handle_startservice_menu(message):
    markup_startservice = types.ReplyKeyboardMarkup(
        row_width=3, one_time_keyboard=True)
    # Add buttons
    button_counter = 1
    for service in services_list:
        button = types.InlineKeyboardButton(f"⏯ Start service: {service}")
        markup_startservice.add(button)
        button_counter += 1
    start_back_button = types.InlineKeyboardButton("🔙 Go back to services")
    markup_startservice.add(start_back_button)

    option_selection_text = "Which service do you want to start?"

    bot.send_message(message.chat.id, option_selection_text,
                     reply_markup=markup_startservice)


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text.startswith("⏯ Start service:"))
def handle_startservice_now(message):
    service = message.text.split(": ")[1]
    logging.info(f"User {message.from_user.first_name} requested service start: {service}")
    bot.reply_to(message, f"Starting {service}.")
    try:
        logging.info(f"Starting {service}.")
        subprocess.run(f"sudo systemctl start {service}", shell=True, text=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Starting {service} failed. Error: {e}")
        print(f"Starting {service} failed. Error: {e}")
        bot.reply_to(message, f"Starting {service} failed. Error: {e}")

    # Get all statuses
    handle_getstatusservices(message)


# Restart a service
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "🟨 Restart a service")
def handle_restartservice_menu(message):
    markup_restartservice = types.ReplyKeyboardMarkup(
        row_width=3, one_time_keyboard=True)
    # Add buttons
    button_counter = 1
    for service in services_list:
        button = types.InlineKeyboardButton(f"🔁 Restart service: {service}")
        markup_restartservice.add(button)
        button_counter += 1

    restart_back_button = types.InlineKeyboardButton("🔙 Go back to services")
    markup_restartservice.add(restart_back_button)

    option_selection_text = "Which service do you want to restart?"

    bot.send_message(message.chat.id, option_selection_text,
                     reply_markup=markup_restartservice)


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text.startswith("🔁 Restart service:"))
def handle_restartservice_now(message):
    service = message.text.split(": ")[1]
    logging.info(f"User {message.from_user.first_name} requested service restart: {service}")
    bot.reply_to(message, f"Restarting {service}.")
    try:
        logging.info(f"Restarting {service}.")
        subprocess.run(f"sudo systemctl restart {service}", shell=True, text=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Restarting {service} failed. Error: {e}")
        print(f"Restarting {service} failed. Error: {e}")
        bot.reply_to(message, f"Restarting {service} failed. Error: {e}")

    # Get all statuses
    handle_getstatusservices(message)

# Stop a service


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "🟥 Stop a service")
def handle_stopservice_menu(message):
    markup_stopservice = types.ReplyKeyboardMarkup(
        row_width=3, one_time_keyboard=True)
    # Add buttons
    button_counter = 1
    for service in services_list:
        button = types.InlineKeyboardButton(f"⛔ Stop service: {service}")
        markup_stopservice.add(button)
        button_counter += 1

    stop_back_button = types.InlineKeyboardButton("🔙 Go back to services")
    markup_stopservice.add(stop_back_button)
    option_selection_text = "Which service do you want to stop?"

    bot.send_message(message.chat.id, option_selection_text,
                     reply_markup=markup_stopservice)


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text.startswith("⛔ Stop service:"))
def handle_stopservice_now(message):
    service = message.text.split(": ")[1]
    logging.info(f"User {message.from_user.first_name} requested service stop: {service}")
    bot.reply_to(message, f"Stopping {service}.")
    try:
        logging.info(f"Stopping {service}.")
        subprocess.run(f"sudo systemctl stop {service}", shell=True, text=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Stopping {service} failed. Error: {e}")
        print(f"Stopping {service} failed. Error: {e}")
        bot.reply_to(message, f"Stopping {service} failed. Error: {e}")

    # Get all statuses
    handle_getstatusservices(message)

# Start all services


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "🟩🟩 Start all services")
def handle_startallservices(message):
    logging.info(f"User {message.from_user.first_name} requested service start all")
    for service in services_list:
        bot.reply_to(message, f"Starting {service}.")
        try:
            logging.info(f"Starting {service}.")
            subprocess.run(f"sudo systemctl start {service}", shell=True, text=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Starting {service} failed. Error: {e}")
            print(f"Starting {service} failed. Error: {e}")
            bot.reply_to(message, f"Starting {service} failed. Error: {e}")

    # Get statuses
    handle_getstatusservices(message)

# Restart all services


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "🟨🟨 Restart all services")
def handle_restartallservices(message):
    logging.info(f"User {message.from_user.first_name} requested service restart all")
    for service in services_list:
        bot.reply_to(message, f"Restarting {service}.")
        try:
            logging.info(f"Restarting {service}.")
            subprocess.run(f"sudo systemctl restart {service}", shell=True, text=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Restarting {service} failed. Error: {e}")
            print(f"Restarting {service} failed. Error: {e}")
            bot.reply_to(message, f"Restarting {service} failed. Error: {e}")

    # Get statuses
    handle_getstatusservices(message)

# Stop all services
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "🟥🟥 Stop all services")
def handle_stopallservices(message):
    logging.info(f"User {message.from_user.first_name} requested service stop all")
    for service in services_list:
        bot.reply_to(message, f"Stopping {service}.")
        try:
            logging.info(f"Stopping {service}.")
            subprocess.run(f"sudo systemctl stop {service}", shell=True, text=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Stopping {service} failed. Error: {e}")
            print(f"Stopping {service} failed. Error: {e}")
            bot.reply_to(message, f"Stopping {service} failed. Error: {e}")

    # Get statuses
    handle_getstatusservices(message)


# DOCKER
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "🐳   Docker")
def handle_docker_menu(message):
    markup_docker_menu = types.ReplyKeyboardMarkup(
        row_width=3, one_time_keyboard=True)

    # Add buttons
    button1 = types.InlineKeyboardButton("🟩 Start a docker container")
    button2 = types.InlineKeyboardButton("🟨 Restart a docker container")
    button3 = types.InlineKeyboardButton("🟥 Stop a docker container")
    button4 = types.InlineKeyboardButton("🟩🟩 Start all docker containers")
    button5 = types.InlineKeyboardButton("🟨🟨 Restart all docker containers")
    button6 = types.InlineKeyboardButton("🟥🟥 Stop all docker containers")
    button7 = types.InlineKeyboardButton("🟫 Get status containers")
    button8 = types.InlineKeyboardButton("🔙 Go back to main")

    markup_docker_menu.add(button1, button2, button3,
                           button4, button5, button6, button7, button8)
    option_selection_text = "What do you want to do?"

    bot.send_message(message.chat.id, option_selection_text,
                     reply_markup=markup_docker_menu)


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text.startswith("🔙 Go back to docker"))
def handle_docker_go_back(message):
    handle_docker_menu(message)


@bot.message_handler(commands=['docker'], func=lambda message: message.chat.id in ALLOWED_USERS)
def send_handle_dockercommand(message):
    handle_docker_menu(message)


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "🟫 Get status containers")
def handle_getdockerstatus(message):
    logging.info(f"User {message.from_user.first_name} requested service get status")
    status_message = "<b>Status containers:</b>"
    # Run the docker ps command, get the NAMES, CREATED, and STATUSES
    try:
        docker_ps_output = subprocess.run(
            'docker ps -a --format "Name: {{.Names}}\nCreated at: {{.CreatedAt}}\nStatus: {{.Status}}\n"',
            shell=True,
            capture_output=True,
            text=True
        )

        # Extract the stdout attribute
        docker_ps_stdout = docker_ps_output.stdout

        status_message += f"\n{docker_ps_stdout}"
        
        logging.info(f"Status message: {status_message}")

        bot.send_message(message.chat.id, status_message, parse_mode="HTML")

    except subprocess.CalledProcessError as e:
        logging.error(f"Get status containers failed. Error: {e}")
        print(f"Get status containers failed. Error: {e}")
        bot.reply_to(
            message, f"Getting container statuses failed. Error: {e}")

    # Go to docker menu
    handle_docker_menu(message)

# Start a docker container
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text.startswith("🟩 Start a docker container"))
def handle_startdockercontainer(message):
    container_names = get_docker_names()
    container_list = container_names.split('\n')[:-1]

    markup_startcontainer = types.ReplyKeyboardMarkup(
        row_width=3, one_time_keyboard=True)
    # Add buttons
    button_counter = 1
    for container in container_list:
        button = types.InlineKeyboardButton(f"⏯ Start container: {container}")
        markup_startcontainer.add(button)
        button_counter += 1
    start_back_button = types.InlineKeyboardButton("🔙 Go back to docker")
    markup_startcontainer.add(start_back_button)

    option_selection_text = "Which service do you want to start?"

    bot.send_message(message.chat.id, option_selection_text,
                     reply_markup=markup_startcontainer)


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text.startswith("⏯ Start container:"))
def handle_startdockercontainer_now(message):
    container = message.text.split(": ")[1]
    logging.info(f"User {message.from_user.first_name} requested docker start: {container}")
    bot.reply_to(message, f"Starting {container}.")
    try:
        logging.info(f"Starting {container}.")
        subprocess.run(f"sudo docker start {container}", shell=True, text=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Starting {container} failed. Error: {e}")
        print(f"Starting {container} failed. Error: {e}")
        bot.reply_to(message, f"Starting {container} failed. Error: {e}")

    # Get all statuses
    handle_getdockerstatus(message)

# Restart a docker container
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text.startswith("🟨 Restart a docker container"))
def handle_restartdockercontainer(message):
    container_names = get_docker_names()
    container_list = container_names.split('\n')[:-1]

    markup_restartcontainer = types.ReplyKeyboardMarkup(
        row_width=3, one_time_keyboard=True)
    # Add buttons
    button_counter = 1
    for container in container_list:
        button = types.InlineKeyboardButton(
            f"🔁 Restart container: {container}")
        markup_restartcontainer.add(button)
        button_counter += 1
    start_back_button = types.InlineKeyboardButton("🔙 Go back to docker")
    markup_restartcontainer.add(start_back_button)

    option_selection_text = "Which service do you want to start?"

    bot.send_message(message.chat.id, option_selection_text,
                     reply_markup=markup_restartcontainer)


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text.startswith("🔁 Restart container:"))
def handle_restartdockercontainer_now(message):
    container = message.text.split(": ")[1]
    logging.info(f"User {message.from_user.first_name} requested docker restart: {container}")
    bot.reply_to(message, f"Restarting {container}.")
    try:
        logging.info(f"Restarting {container}.")
        subprocess.run(f"sudo docker restart {container}", shell=True, text=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Restarting {container} failed. Error: {e}")
        print(f"Restarting {container} failed. Error: {e}")
        bot.reply_to(message, f"Restarting {container} failed. Error: {e}")

    # Get all statuses
    handle_getdockerstatus(message)


# Stop a docker container
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text.startswith("🟥 Stop a docker container"))
def handle_stopdockercontainer(message):
    container_names = get_docker_names()
    container_list = container_names.split('\n')[:-1]

    markup_stopcontainer = types.ReplyKeyboardMarkup(
        row_width=3, one_time_keyboard=True)
    # Add buttons
    button_counter = 1
    for container in container_list:
        button = types.InlineKeyboardButton(f"⛔ Stop container: {container}")
        markup_stopcontainer.add(button)
        button_counter += 1
    start_back_button = types.InlineKeyboardButton("🔙 Go back to docker")
    markup_stopcontainer.add(start_back_button)

    option_selection_text = "Which service do you want to stop?"

    bot.send_message(message.chat.id, option_selection_text,
                     reply_markup=markup_stopcontainer)


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text.startswith("⛔ Stop container:"))
def handle_stopcontainer_now(message):
    container = message.text.split(": ")[1]
    logging.info(f"User {message.from_user.first_name} requested docker stop: {container}")
    bot.reply_to(message, f"Stopping {container}.")
    try:
        logging.info(f"Stopping {container}.")
        subprocess.run(f"sudo docker stop {container}", shell=True, text=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Stopping {container} failed. Error: {e}")
        print(f"Stopping {container} failed. Error: {e}")
        bot.reply_to(message, f"Stopping {container} failed. Error: {e}")

    # Get all statuses
    handle_getdockerstatus(message)

# Start all docker containers


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "🟩🟩 Start all docker containers")
def handle_startalldockercontainers(message):
    logging.info(f"User {message.from_user.first_name} requested docker start all")
    container_names = get_docker_names()
    container_list = container_names.split('\n')[:-1]
    

    for container in container_list:
        bot.reply_to(message, f"Starting {container}.")
        try:
            logging.info(f"Starting {container}.")
            subprocess.run(f"docker start {container}", shell=True, text=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Starting {container} failed. Error: {e}")
            print(f"Starting {container} failed. Error: {e}")
            bot.reply_to(message, f"Starting {container} failed. Error: {e}")

    # Get statuses
    handle_getdockerstatus(message)

# Restart all docker containers
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "🟨🟨 Restart all docker containers")
def handle_restartalldockercontainers(message):
    logging.info(f"User {message.from_user.first_name} requested docker restart all")
    container_names = get_docker_names()
    container_list = container_names.split('\n')[:-1]

    for container in container_list:
        bot.reply_to(message, f"Restarting {container}.")
        try:
            logging.info(f"Restarting {container}.")
            subprocess.run(f"docker restart {container}", shell=True, text=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Restarting {container} failed. Error: {e}")
            print(f"Restarting {container} failed. Error: {e}")
            bot.reply_to(message, f"Restarting {container} failed. Error: {e}")

    # Get statuses
    handle_getdockerstatus(message)

# Stop all docker containers
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "🟥🟥 Stop all docker containers")
def handle_stopalldockercontainers(message):
    logging.info(f"User {message.from_user.first_name} requested docker stop all")
    container_names = get_docker_names()
    container_list = container_names.split('\n')[:-1]

    for container in container_list:
        bot.reply_to(message, f"Stopping {container}.")
        try:
            logging.info(f"Stopping {container}.")
            subprocess.run(f"docker stop {container}", shell=True, text=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Stopping {container} failed. Error: {e}")
            print(f"Stopping {container} failed. Error: {e}")
            bot.reply_to(message, f"Stopping {container} failed. Error: {e}")

    time.sleep(1)
    # Get statuses
    handle_getdockerstatus(message)


def get_docker_names():
    logging.info(f"Getting container names")
    # Run the docker ps command, get the NAMES, CREATED, and STATUSES
    try:
        docker_ps_output = subprocess.run(
            'docker ps -a --format {{.Names}}',
            shell=True,
            capture_output=True,
            text=True
        )

        # Extract the stdout attribute
        docker_ps_stdout = docker_ps_output.stdout

        names = f"{docker_ps_stdout}"
        
        logging.info(f"Container names: {names}")
        return names

    except subprocess.CalledProcessError as e:
        logging.error(f"Getting container names failed. Error: {e}")
        print(f"Getting container names failed. Error: {e}")
        for chat_id in ALLOWED_USERS:
            bot.send_message(chat_id, f"Getting container names failed. Error: {e}")
        return []

# LOGS
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "📜       Logs")
def handle_logs_menu(message):
    markup_logs_menu = types.ReplyKeyboardMarkup(
        row_width=4, one_time_keyboard=True)

    # Add buttons
    button_counter = 1
    for log_file in log_files:
        button = types.InlineKeyboardButton(f"📜 Log: {log_file}")
        markup_logs_menu.add(button)
        button_counter += 1

    logs_back_button = types.InlineKeyboardButton("🔙 Go back to main")
    markup_logs_menu.add(logs_back_button)
    option_selection_text = "Which log file do you want to see?"

    bot.send_message(message.chat.id, option_selection_text,
                     reply_markup=markup_logs_menu)


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text.startswith("📜 Log: "))
def handle_logs(message):
    logging.info(f"User {message.from_user.first_name} requested log file {message.text.split(': ')[1]}")
    log_directory = f"{message.text.split(': ')[1]}/"
    logging.info(f"Log directory: {log_directory}")

    # List all files in the log directory
    log_files = glob(os.path.join(log_directory, '*.log'))
    logging.info(f"Log files: {log_files}")

    if not log_files:
        bot.send_message(message.chat.id, "No log files found.")
        # Open logs menu
        handle_logs_menu(message)
        return
    
    # Filter out log files with date suffixes
    log_files_without_date = [file for file in log_files if not any(date_str in file for date_str in ['-01-', '-02-', '-03-', '-04-', '-05-', '-06-', '-07-', '-08-', '-09-', '-10-', '-11-', '-12-'])]

    if not log_files_without_date:
        bot.send_message(message.chat.id, "No log files without a date suffix found.")
        # Open logs menu
        handle_logs_menu(message)
        return

    # Select the log file without a date suffix
    log_file = log_files_without_date[0]

    # Convert log file to text file
    text_file = log_file.replace('.log', '.txt')

    with open(log_file, 'r') as log_file_content:
        with open(text_file, 'w') as text_file_content:
            text_file_content.write(log_file_content.read())

    bot.send_document(message.chat.id, open(text_file, 'rb'))

    # Optionally, you can remove the created text file after sending if needed
    os.remove(text_file)

    # Also send the tail of the log file
    with open(log_file, 'r') as f:
        log_lines = f.readlines()
        bot.send_message(message.chat.id, "Last 20 lines of the log file:")
        bot.send_message(message.chat.id, "\n".join(log_lines[-20:]))

    # Open logs menu
    handle_logs_menu(message)


@bot.message_handler(commands=['logs'], func=lambda message: message.chat.id in ALLOWED_USERS)
def send_handle_logs(message):
    handle_logs_menu(message)

# SEND CUSTOM COMMAND
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "📤 Send command")
# Reply that the next message will be sent as a command to the server
def handle_send_command(message):
    bot.reply_to(
        message, "What command do you want to send to the server? Send /cancel to exit")
    bot.register_next_step_handler(message, handle_command)


def handle_command(message):
    logging.info(f"User {message.from_user.first_name} sent a command: {message.text}")
    command = message.text
    logging.debug(f"Sending command: {command}")
    bot.reply_to(message, f"Sending command: {command}")
    
    if command.lower() == "/cancel" or command.lower() == "cancel":
        send_handle_menu(message)
        return
    
    try:
        command_output = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )

        # Extract the stdout attribute
        command_stdout = command_output.stdout

        # Escape the text to prevent Telegram from interpreting it as entities
        command_stdout_escaped = html.escape(command_stdout)

        # Split the output into chunks of 10 lines
        lines = command_stdout_escaped.split('\n')
        chunks = [textwrap.dedent('\n'.join(lines[i:i+10]))
                  for i in range(0, len(lines), 10)]
        
        logging.debug(f"Command output: {command_stdout_escaped}")

        # If the output is empty, send a message indicating that
        if not chunks:
            bot.send_message(message.chat.id, "The command output is empty.")
        else:
            # Send each chunk separately
            for chunk in chunks:
                bot.send_message(message.chat.id, chunk)

        handle_send_command(message)
    except subprocess.CalledProcessError as e:
        logging.error(f"Sending command failed. Error: {e}")
        bot.reply_to(message, f"Sending command failed. Error: {e}")


@bot.message_handler(commands=['command'], func=lambda message: message.chat.id in ALLOWED_USERS)
def send_handle_command(message):
    handle_send_command(message)

# CHECK SERVERS
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "🔔 Check servers")
def handle_check_servers_menu(message):
    markup_check_servers_menu = types.ReplyKeyboardMarkup(
        row_width=4, one_time_keyboard=True)
    
    for server in servers_list:
        server_name = server.split('=')[0]
        button = types.InlineKeyboardButton(f"🔔 Ping: {server_name}")
        markup_check_servers_menu.add(button)

    check_servers_back_button = types.InlineKeyboardButton("🔙 Go back to main")
    markup_check_servers_menu.add(check_servers_back_button)
    option_selection_text = "Which server do you want to ping?"

    bot.send_message(message.chat.id, option_selection_text,
                     reply_markup=markup_check_servers_menu)

@bot.message_handler(commands=['ping'], func=lambda message: message.chat.id in ALLOWED_USERS)
def send_handle_check_servers(message):
    handle_check_servers_menu(message)
    
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text.startswith("🔔 Ping: "))
def handle_check_servers(message):
    chosen_server_name = message.text.split(": ")[1]
    logging.info(f"User {message.from_user.first_name} requested server check for {chosen_server_name}...")
    for server in servers_list:
        server_name = server.split('=')[0]
        server_ip_port = server.split('=')[1]
        server_ip = server_ip_port.split(':')[0]
        port = server_ip_port.split(':')[1]
        if chosen_server_name == server_name:
            bot.send_message(message.chat.id, f"Pinging {server_name} at port {port}...")
            ping_server(server_name, server_ip, port, message)

def ping_server(server_name, server_ip, port, message):
    logging.info(f"Pinging {server_name} at port {port}...")
    time_out = 5
    ping_output = subprocess.run(f'nc -zv -{time_out} {server_ip} {port}', shell=True, capture_output=True, text=True, timeout=10)
    
    try:
        with open(server_states_json, 'r') as json_file:
            previous_server_states = json.load(json_file)
    except FileNotFoundError:
        previous_server_states = {}

    current_server_states = previous_server_states    
    
    # Check if output contains 'failed' or 'succeeded'    
    if 'succeeded' in str(ping_output) or 'open' in str(ping_output):
        print(f"Server {server_name} is online.")
        logging.info(f"Server {server_name} is online.")
        logging.info(f"Output: {str(ping_output)}")
        
        if server_name in previous_server_states:
            if previous_server_states[server_name] == 'offline' or previous_server_states[server_name] == 'unknown':
                bot.send_message(message.chat.id, f"✅ Server {server_name} is back online.")
            else:
                bot.send_message(message.chat.id, f"✅ Server {server_name} is online.")
        else:
            bot.send_message(message.chat.id, f"✅ Server {server_name} is online.")
                
                
        current_server_states[server_name] = 'online'
           
    else:
        time.sleep(5)
        time_out2 = 10
        ping_output2 = subprocess.run(f'nc -zv -w {time_out2} {server_ip} {port}', shell=True, capture_output=True, text=True, timeout=10)
        if 'succeeded' in str(ping_output2):
            print(f"Server {server_name} is online.")
            logging.info(f"Server {server_name} is online.")
            logging.info(f"Output: {str(ping_output2)}")
            
            if server_name in previous_server_states:
                if previous_server_states[server_name] == 'offline' or previous_server_states[server_name] == 'unknown':
                    bot.send_message(message.chat.id, f"✅ Server {server_name} is back online.")
                else:
                    bot.send_message(message.chat.id, f"✅ Server {server_name} is online.")
            else:
                bot.send_message(message.chat.id, f"✅ Server {server_name} is online.")            
            
            current_server_states[server_name] = 'online'
            
        elif 'failed' in str(ping_output2) or 'timed out' in str(ping_output2):      
            print(f"Server {server_name} is offline.")
            logging.info(f"Server {server_name} is offline.")
            logging.info(f"Output: {str(ping_output2)}")
            bot.send_message(message.chat.id, f"⚠️ Server {server_name} is offline!") 
            current_server_states[server_name] = 'offline'
        else:
            print(f"Status of server {server_name} is unknown.")
            logging.info(f"Status of server {server_name} is unknown.")
            logging.info(f"Output: {str(ping_output2)}")
            bot.send_message(message.chat.id, f"⚠️ Status of server {server_name} is unknown!")
            bot.send_message(message.chat.id, f"Output: {str(ping_output2)}")
            current_server_states[server_name] = 'unknown'

    save_server_states_to_json(current_server_states)
 
 
# SYSTEM INFO
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "📃 System info")
def handle_system_info(message):
    
    logging.info(f"User {message.from_user.first_name} requested the system info")
    bot.reply_to(message, "Getting system info.")
    command = """
    echo "CPU Usage:"
    top -b -n 1 | awk '/^%Cpu/ {print "Usage: " 100 - $8 "%"}'
    
    echo "\nMemory Usage:"
    free -m | awk '/^Mem/ {print "Total: " $2 "MB\tUsed: " $3 "MB\tFree: " $4 "MB\tCache: " $6 "MB"}'
    
    echo "\nDisk Usage (Total, Used, Free):"
    df -h 2>/dev/null | grep /dev/ | awk '{print "Total: " $2 "\tUsed: " $3 " (" $5 ") \tFree: " $4}'
    
    echo "\nCurrent Temperature:"
    cat /sys/class/thermal/thermal_zone0/temp | awk '{print "Temperature: " $1/1000 "°C"}'
    
    echo "\nCurrent Fan state:"
    cat /sys/class/thermal/cooling_device0/cur_state | awk '{print "Fan state: " $1}'

    echo "\nAvailable Updates:"
    if command -v apt &> /dev/null; then
      sudo apt list --upgradable 2>/dev/null | grep -c '/'
    elif command -v yum &> /dev/null; then
      sudo yum list updates 2>/dev/null | grep -c '\\.'
    else
      echo "Unsupported package manager"
    fi

    echo "\nSystem Uptime:"
    uptime
    """

    logging.debug(f"Sending command: {command}")
    reply_message = "<b>System info:</b>\n"
    try:
        command_output = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )

        # Extract the stdout attribute
        command_stdout = command_output.stdout

        # Escape the text to prevent Telegram from interpreting it as entities
        command_stdout_escaped = html.escape(command_stdout)

        # Split the output into chunks of 10 lines
        lines = command_stdout_escaped.split('\n')
        chunks = [textwrap.dedent('\n'.join(lines[i:i+10]))
                  for i in range(0, len(lines), 10)]
        
        logging.debug(f"Command output: {command_stdout_escaped}")

        # If the output is empty, send a message indicating that
        if not chunks:
            bot.send_message(message.chat.id, "The command output is empty.")
        else:
            # Concatenate all chunks into one message
            full_output = '\n'.join(chunks)
            # Remove the line with "/usr/bin/apt"
            full_output = '\n'.join(line for line in full_output.split('\n') if "/usr/bin/apt" not in line)
            reply_message += full_output
            
            bot.send_message(message.chat.id, reply_message)

        send_handle_menu(message)
    except subprocess.CalledProcessError as e:
        logging.error(f"Sending command system info failed. Error: {e}")
        print(f"Sending command system info failed. Error: {e}")    
        bot.reply_to(message, f"Sending command system info failed. Error: {e}")
        # Go back to the main menu
        send_handle_menu(message)


@bot.message_handler(commands=['sysinfo'], func=lambda message: message.chat.id in ALLOWED_USERS)
def send_handle_system_info(message):
    handle_system_info(message)

    
## STRESS TEST
@bot.message_handler(func=lambda msg: msg.chat.id in ALLOWED_USERS and msg.text == "💪 Stress test")
def handle_stress_test(msg):
    prompt = bot.send_message(msg.chat.id, "Enter the number of minutes for the stress test:")
    bot.register_next_step_handler(prompt, run_stress_test)

def run_stress_test(msg):
    if msg.text.isdigit() and int(msg.text) > 0:
        seconds = int(msg.text) * 60
        bot.send_message(msg.chat.id, f"Stress test started for {msg.text} minutes.")
        response = subprocess.run(
            ["stress-ng", "--cpu", "4", "--timeout", f"{seconds}s"],
            capture_output=True, text=True
        )
        bot.send_message(msg.chat.id, f"Response:\n{response.stdout or response.stderr}")
    else:
        bot.send_message(msg.chat.id, "Please enter a valid number greater than 0.")
    
    send_handle_menu(msg)

# FAN STATE
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "💨 Fan state")
def handle_fan_state(message):
    logging.info(f"User {message.from_user.first_name} requested fan state")
    markup_menu = types.ReplyKeyboardMarkup(
    row_width=2, one_time_keyboard=True)
    
    fan_state_0 = types.InlineKeyboardButton("💨 Set fans state 0: Off")
    fan_state_1 = types.InlineKeyboardButton("💨 Set fans state 1: On")
    back = types.InlineKeyboardButton("🔙 Go back to main")
    
    markup_menu.add(fan_state_0, fan_state_1, back)
    
    option_selection_text = "Choose one of the following options:"
    
    bot.send_message(message.chat.id, option_selection_text,
                     reply_markup=markup_menu)
    
    bot.register_next_step_handler(message, handle_fan_state_option)
    
def handle_fan_state_option(message):
    logger.info(f"User {message.from_user.first_name} selected fan state option: {message.text}")
    
    if message.text == "🔙 Go back to main":
        send_handle_menu(message)
        return
    
    if message.text == "💨 Set fans state 0: Off":
        state = 0
        new_message = "💨 fans state to 0: Off (automatic)"
    elif message.text == "💨 Set fans state 1: On":
        state = 1
        new_message = "💨 fans state 1: On"
    else:
        bot.send_message(message.chat.id, "Invalid option selected. Please try again.")
        send_handle_menu(message)
        return
        
    bot.send_message(message.chat.id, f"Setting {new_message}...")
        
    command = f"echo {state} | sudo tee /sys/class/thermal/cooling_device0/cur_state"
    
    try:
        command_output = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )

        # If output was successful, send a message indicating that
        if command_output.returncode == 0:
            bot.send_message(message.chat.id, f"💨 Fans state changed to {new_message}.")
        else:
            logging.error(f"Setting fans state failed. Error: {command_output.stderr}")
            bot.reply_to(message, f"Setting fans state failed. Error: {command_output.stderr}")

        send_handle_menu(message)
    except subprocess.CalledProcessError as e:
        logging.error(f"Setting fans state failed. Error: {e}")
        bot.reply_to(message, f"Setting fans state failed. Error: {e}")

# REBOOT
@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "🔁 Reboot")
def handle_reboot_menu(message):
    markup_reboot = types.ReplyKeyboardMarkup(
        row_width=2, one_time_keyboard=True)
    # Add buttons
    button1 = types.InlineKeyboardButton("🔁 Reboot now")
    button2 = types.InlineKeyboardButton("❌ Cancel reboot")

    markup_reboot.add(button1, button2)
    option_selection_text = "Are you sure you want to reboot the server?"

    bot.send_message(message.chat.id, option_selection_text,
                     reply_markup=markup_reboot)


@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "🔁 Reboot now")
def handle_reboot_now(message):
    logging.info(f"User {message.from_user.first_name} requested a reboot")
    bot.reply_to(message, "Rebooting the server.")
    try:
        logging.info(f"Rebooting the server.")
        subprocess.run(f"sudo reboot now", shell=True, check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Rebooting failed. Error: {e}")
        print(f"Rebooting failed. Error: {e}")
        bot.reply_to(message, f"Rebooting failed. Error: {e}")

@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_USERS and message.text == "❌ Cancel reboot")
def handle_cancel_reboot(message):
    logging.info(f"User {message.from_user.first_name} canceled the reboot")
    bot.reply_to(message, "Reboot canceled.")


@bot.message_handler(commands=['reboot'], func=lambda message: message.chat.id in ALLOWED_USERS)
def send_handle_reboot(message):
    handle_reboot_menu(message) 
 
    
def save_server_states_to_json(server_states):
    with open(server_states_json, 'w') as json_file:
        json.dump(server_states, json_file)
    

@bot.message_handler(func=lambda message: True)
def handle_all_other_messages(message):
    logging.debug(f"Handle_all_other_messages function started.\n\n")
    # Code to execute for all other messages
    bot.reply_to(message, "I'm sorry, I don't understand that command.")

    logging.info("I'm sorry, I don't understand that command.")
    logging.debug(f"Handle_all_other_messages function ended.\n\n")

print("Bot running...")
logging.info("Bot running...")
bot.polling()
