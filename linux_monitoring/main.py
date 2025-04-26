import os
import time
import subprocess
import telebot
from dotenv import load_dotenv
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
import schedule
import json

# ENV VARIABLES
# Load environment variables from .env
load_dotenv(dotenv_path='../.env')

# Telegram bot setup
SECRET_TOKEN = os.environ.get('SECRET_TOKEN')
bot = telebot.TeleBot(SECRET_TOKEN)
CHAT_ID_PERSON1 = int(os.environ.get('CHAT_ID_PERSON1'))
ALLOWED_USERS = [CHAT_ID_PERSON1]

# LOGGING
log_directory = './logs/'
log_file_path = os.path.join(log_directory, 'monitoring.log')

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

# SERVICES
# Function to check and restart services
def check_and_restart_services(service_list):
    logging.info("Checking and restarting services.")
    for service in service_list:        
        if not is_service_running(service):
            print(f"Service {service} is not running.")
            logging.info(f"Service {service} is not running.")
            restart_service(service)
        else:
            print(f"Service {service} is running. No need to restart.")
            logging.info(f"Service {service} is running. No need to restart.")
        

# Function to check if a service is running
def is_service_running(service_name):
    try:
        print(f"Checking {service_name}...")
        logging.info(f"Checking {service_name}...")
        
        service_status_output = subprocess.run(f'systemctl status {service_name} | grep "Active:" | awk \'{{print "{service_name}:", $2, $3}}\'', shell=True, capture_output=True, text=True)
        service_status = service_status_output.stdout.split(' ')[1]
        
        print(f"{service_name} is {service_status}")
        logging.info(f"{service_name} is {service_status}")
        
        if service_status == 'active':
            return True
        else:
            return False
    except subprocess.CalledProcessError as e:
        print(f"Error while checking service {service_name}: {str(e)}")
        logging.error(f"Error while checking service {service_name}: {str(e)}")
        send_telegram_message(f"Error while checking service {service_name}: {str(e)}")
        return False

# Function to restart a service
def restart_service(service_name):
    try:
        print(f"Restarting {service_name}...")
        logging.info(f"Restarting {service_name}...")
        
        subprocess.run(f'systemctl restart {service_name}', shell=True, text=True)
                
        if is_service_running(service_name):
            print(f"Service {service_name} was down, but was restarted successfully.")
            logging.info(f"Service {service_name} was restarted successfully.")
            send_telegram_message(f"🦾 📦 Service {service_name}  was down, but I have restarted it successfully.")
        else:
            print(f"Service {service_name} was down, and could not be restarted.")
            logging.info(f"Service {service_name} was down, and could not be restarted.")
            send_telegram_message(f"😓 📦 Service {service_name} is down, and I was not able to restart it. Please help me!")
    except Exception as e:
        print(f"Error while restarting service {service_name}: {str(e)}")
        logging.error(f"Error while restarting service {service_name}: {str(e)}")
        send_telegram_message(f"😨 📦 Service {service_name} is down, but while restarting it, I encountered an error: {str(e)}")

#DOCKER
# Function to check and restart Docker containers
def check_and_restart_containers(container_list):
    logging.info("Checking and restarting containers.")
    for container in container_list:        
        if not is_container_running(container):
            print(f"Container {container} is not running.")
            logging.info(f"Container {container} is not running.")
            restart_container(container)
        else:
            print(f"{container} is running. No need to restart.")
            logging.info(f"{container} is running. No need to restart.")

# Function to check if a Docker container is running
def is_container_running(container_name):
    try:
        print(f"Checking {container_name} running...")
        logging.info(f"Checking {container_name}...")
        command = f'docker ps -a --filter "name={container_name}"'
        
        container_status_output = subprocess.run(command, shell=True, capture_output=True, text=True).stdout.strip()
        status_line = container_status_output.split('\n')[-1]
        # Split the line into columns
        columns = status_line.split()
        
        # Check if "Up" is present in the list
        if 'Up' in columns:
            container_status = 'Up'
        elif 'Exited' in columns:
            container_status = 'Exited'
        else:
            container_status = 'unknown'
                
        print(f"{container_name} is {container_status}")
                
        if container_status == 'Up':
            return True
        else:
            return False
    except subprocess.CalledProcessError as e:
        print(f"Error while checking container {container_name}: {str(e)}")
        logging.error(f"Error while checking container {container_name}: {str(e)}")
        # You may want to handle the error and notify accordingly (e.g., send_telegram_message)
        return False


# Function to restart a Docker container
def restart_container(container_name):
    try:
        print(f"Restarting {container_name}...")
        logging.info(f"Restarting {container_name}...")
        
        subprocess.run(f'docker start {container_name}', shell=True, text=True)
        time.sleep(5)
        if is_container_running(container_name):
            print(f"Container {container_name} was down, but was restarted successfully.")
            logging.info(f"Container {container_name} was restarted successfully.")
            send_telegram_message(f"🦾 🐳 Container {container_name} was down, but I have restarted it successfully.")
        else:
            print(f"Container {container_name} was down, and could not be restarted.")
            logging.info(f"Container {container_name} was down, and could not be restarted.")
            send_telegram_message(f"😓 🐳 container {container_name} is down, and I was not able to restart it. Please help me!")
    except Exception as e:
        print(f"Error while restarting container {container_name}: {str(e)}")
        logging.error(f"Error while restarting container {container_name}: {str(e)}")
        send_telegram_message(f"😨 🐳 Container {container_name} is down, but while restarting it, I encountered an error: {str(e)}")

# Function to ping server
def are_servers_online(server_list):
    try:
        with open('server_states.json', 'r') as json_file:
            previous_server_states = json.load(json_file)
    except FileNotFoundError:
        previous_server_states = {}
        
    current_server_states = {}    
    
    for server in server_list:
        server_name = server.split('=')[0]
        server_ip_port = server.split('=')[1]
        server_ip = server_ip_port.split(':')[0]
        port = server_ip_port.split(':')[1]
        
        logging.info(f"Pinging {server_name} at port {port}...")
        time_out = 5
        ping_output = subprocess.run(f'nc -zv -w {time_out} {server_ip} {port}', shell=True, capture_output=True, text=True)
        
        # Check if output contains 'failed' or 'succeeded'    
        if 'succeeded' in str(ping_output) or 'open' in str(ping_output):
            print(f"Server {server_name} is online.")
            logging.info(f"Server {server_name} is online.")
            logging.info(f"Output: {str(ping_output)}")
            
            if server_name in previous_server_states:
                if previous_server_states[server_name] == 'offline' or previous_server_states[server_name] == 'unknown':
                    send_telegram_message(f"✅ Server {server_name} is back online.")
                    
            current_server_states[server_name] = 'online'
        else:
            time.sleep(5)
            time_out2 = 10
            ping_output2 = subprocess.run(f'nc -zv -w {time_out2} {server_ip} {port}', shell=True, capture_output=True, text=True)
            if 'succeeded' in str(ping_output2):
                print(f"Server {server_name} is online.")
                logging.info(f"Server {server_name} is online.")
                logging.info(f"Output: {str(ping_output2)}")
                
                if server_name in previous_server_states:
                    if previous_server_states[server_name] == 'offline' or previous_server_states[server_name] == 'unknown':
                        send_telegram_message(f"✅ Server {server_name} is back online.")                
                current_server_states[server_name] = 'online'
                
            elif 'failed' in str(ping_output2):      
                print(f"Server {server_name} is offline.")
                logging.info(f"Server {server_name} is offline.")
                logging.info(f"Output: {str(ping_output2)}")
                current_server_states[server_name] = 'offline'
                send_telegram_message(f"⚠️ Server {server_name} is offline!") 
            else:
                print(f"Status of server {server_name} is unknown.")
                logging.info(f"Status of server {server_name} is unknown.")
                logging.info(f"Output: {str(ping_output2)}")
                current_server_states[server_name] = 'unknown'
                send_telegram_message(f"⚠️ Status of server {server_name} is unknown!")
                send_telegram_message(f"Output: {str(ping_output2)}")

    save_server_states_to_json(current_server_states)
    
def save_server_states_to_json(server_states):
    logging.info(f"Saving server states to JSON file: {server_states}")
    with open('server_states.json', 'w') as json_file:
        json.dump(server_states, json_file)
        
# Function to check storage usage        
def check_storage_usage():
    command = 'df -h / | awk \'NR==2{print $5}\''
    storage_threshold = 90
    
    storage_usage = subprocess.run(command, shell=True, capture_output=True, text=True).stdout.strip().split('%')[0]
    print(f"Storage usage: {storage_usage}%")
    logging.info(f"Storage usage: {storage_usage}%")
    
    if int(storage_usage) > storage_threshold:
        send_telegram_message(f"💾 Storage usage is high (> {storage_threshold}%).")
        
# Function to check CPU usage
def check_cpu_usage():
    command = 'top -bn 1 | awk \'/Cpu\(s\):/ {print "%Cpu: " $2}\''

    cpu_usage = subprocess.run(command, shell=True, capture_output=True, text=True).stdout.strip().split(': ')[1]
    print(f"CPU usage: {cpu_usage}%")
    logging.info(f"CPU usage: {cpu_usage}%")
    if (float(cpu_usage) > 80):
        time.sleep(5)
        
        cpu_usage2 = subprocess.run(command, shell=True, capture_output=True, text=True).stdout.strip().split(': ')[1]
        if (float(cpu_usage2) > 80):
            top_consumers = subprocess.run('ps -eo pid,%cpu,%mem,comm --sort=-%cpu | head -n 11', shell=True, capture_output=True, text=True).stdout
            
            print(f"CPU usage: {cpu_usage2}%")
            logging.info(f"CPU usage: {cpu_usage2}%")
            logging.info(f"Top consumers: \n{top_consumers}")
            send_telegram_message(f"🔥 CPU usage is high (> 80%). First time it was {cpu_usage}% and after 30 seconds it was {cpu_usage2}%. These are the top consumers: \n<pre>{top_consumers}</pre>", "HTML")

# Check temperature
def check_temperature():
    command = 'cat /sys/class/thermal/thermal_zone0/temp | awk \'{print "Temperature: " $1/1000 "°C"}\''
    temperature = subprocess.run(command, shell=True, capture_output=True, text=True).stdout.strip()
    print(f"{temperature}")
    logging.info(f"{temperature}")
    
    temperature_float = temperature.split('Temperature: ')[1].split('°C')[0]
    
    if (float(temperature_float) > 50):
        # Check if fans are turned on
        command = 'cat /sys/class/thermal/cooling_device0/cur_state | awk \'{print "Fans state: " $1}\''
        fans_state = subprocess.run(command, shell=True, capture_output=True, text=True).stdout.strip()
        print(f"Fans state: {fans_state}")
        logging.info(f"Fans state: {fans_state}")
        
        if (fans_state != "1"):
            send_telegram_message(f"🌡️ Temperature is high (> 50°C). Current temperature is {temperature_float}. Fans are not turned on: {fans_state}", "HTML")
        else:
            send_telegram_message(f"🌡️ Temperature is high (> 50°C). Current temperature is {temperature_float}. Fans are turned on: {fans_state}", "HTML")

# Function to send messages to Telegram
def send_telegram_message(message, parse_mode=None):
    try:
        for chat_id in ALLOWED_USERS:
            bot.send_message(chat_id, message, parse_mode=parse_mode)
    except Exception as e:
        print(f"Error while sending Telegram message: {str(e)}")
        logging.error(f"Error while sending Telegram message: {str(e)}")


# Run every 5 minutes
def job():
    # Read service and container lists from files
    with open('monitoring_services.txt', 'r') as services_file:
        services_list = services_file.read().splitlines()

    with open('monitoring_containers.txt', 'r') as containers_file:
        containers_list = containers_file.read().splitlines()
        
    with open('monitoring_servers.txt', 'r') as servers_file:
        servers_list = servers_file.read().splitlines()
    
    print("Starting monitoring...")
    logging.info("Starting monitoring...")
    check_and_restart_services(services_list)
    check_and_restart_containers(containers_list)
    are_servers_online(servers_list)
    check_cpu_usage()
    check_temperature()
    check_storage_usage()
    print("Monitoring finished. See you in 5 minutes.")
    logging.info("Monitoring finished. See you in 5 minutes.")


job()

# Schedule the job to run at the specified intervals (5 minute intervals, 00:00, 00:05 etc.)
five_minute_intervals = ["{:02d}:{:02d}".format(hour, minute) for hour in range(24) for minute in range(0, 60, 5)]

for interval in five_minute_intervals:
    schedule.every().day.at(interval).do(job)

# Run the scheduler
while True:
    schedule.run_pending()
    time.sleep(1)

