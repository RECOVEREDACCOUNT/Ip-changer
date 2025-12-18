import requests
import os
from time import sleep, time
import sys
import threading
import signal

class colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    PINK = '\033[95m'
    HACKER_GREEN = '\033[92m'

exit_flag = False

def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

def signal_handler(sig, frame):
    global exit_flag
    exit_flag = True
    
    sys.stdout.write("\r\033[K\033[A")
    sys.stdout.flush()
    
    print("\n" + colors.WARNING + "Exit requested..." + colors.ENDC)
    
    try:
        confirm = input(colors.BOLD + "Exit? (y/n): " + colors.ENDC).lower()
        if confirm == 'y' or confirm == 'yes':
            sys.stdout.write("\r\033[K")
            print(colors.OKGREEN + "Exiting cleanly. Goodbye!" + colors.ENDC)
            os._exit(0)
        else:
            print(colors.OKBLUE + "Continuing...\n" + colors.ENDC)
            exit_flag = False
    except (EOFError, KeyboardInterrupt):
        sys.stdout.write("\r\033[K")
        print(colors.OKGREEN + "\nExiting cleanly. Goodbye!" + colors.ENDC)
        os._exit(0)

def check_tor_service():
    try:
        print(colors.OKBLUE + "\nChecking Tor Service." + colors.ENDC)
        response = os.system("service tor status > /dev/null 2>&1")
        if response != 0:
            print(colors.FAIL + "Tor Service Running X" + colors.ENDC)
            start_tor_service()
        else:
            print(colors.OKGREEN + "Tor Service Running ✔" + colors.ENDC)
    except Exception as e:
        print(colors.FAIL + "\nFailed to check Tor service status: {}".format(e) + colors.ENDC)
        sys.exit(1)

def start_tor_service():
    try:
        sys.stdout.write("\r" + colors.BOLD + colors.OKBLUE + "Starting Tor Service" + colors.ENDC)
        for i in range(1, 101):
            sys.stdout.write("\r" + colors.BOLD + colors.HACKER_GREEN + f"Starting Tor Service: [{'#' * (i // 5)}{' ' * ((100 - i) // 5)}] {i}%" + colors.ENDC)
            sys.stdout.flush()
            sleep(0.1)
        os.system("sudo service tor start > /dev/null 2>&1")
        print("\n" + colors.OKGREEN + "Tor service started successfully." + colors.ENDC)
        clear_terminal()
    except Exception as e:
        print(colors.FAIL + "\nFailed to start Tor service: {}".format(e) + colors.ENDC)
        sys.exit(1)

def change_ip():
    """Change IP by reloading Tor"""
    os.system("sudo service tor reload > /dev/null 2>&1")
    sleep(2)

def spinner_effect():
    spinner = ['|', '/', '-', '\\']
    i = 0
    while not exit_flag:
        sys.stdout.write("\r" + colors.BOLD + "Virtual? " + colors.OKCYAN + spinner[i] + colors.ENDC)
        sys.stdout.flush()
        sleep(0.1)
        i = (i + 1) % 4

def format_time(seconds):
    """Convert seconds to readable format"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}m {secs}s" if secs > 0 else f"{mins}m"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m" if mins > 0 else f"{hours}h"

def Main():
    signal.signal(signal.SIGINT, signal_handler)
    
    clear_terminal()
    print(colors.PINK + """
████████╗ ██████╗ ██████╗        ░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░
╚══██╔══╝██╔═══██╗██╔══██╗       ░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░
   ██║   ██║   ██║██████╔╝       ░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░
   ██║   ██║   ██║██╔══██╗       ░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░
   ██║   ╚██████╔╝██║  ██║       ░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░
   ╚═╝    ╚═════╝ ╚═╝  ╚═╝        ░▒▓███████▓▒░░▒▓███████▓▒░░▒▓█▓▒░
""" + colors.ENDC)
    
    check_tor_service()
    
    try:
        interval = int(input(colors.WARNING + "\nChange interval (seconds): " + colors.ENDC))
    except ValueError:
        print(colors.FAIL + "Invalid input. Please enter a number." + colors.ENDC)
        sys.exit(1)
    except KeyboardInterrupt:
        print(colors.OKGREEN + "\n\nExiting cleanly. Goodbye!" + colors.ENDC)
        os._exit(0)
    
    url = "https://httpbin.org/ip"
    proxy = {'http':'socks5://127.0.0.1:9050', 'https':'socks5://127.0.0.1:9050'}
    
    spinner_thread = threading.Thread(target=spinner_effect, daemon=True)
    spinner_thread.start()
    
    start_time = time()
    change_count = 0
    
    print(colors.OKBLUE + f"\n>> Running indefinitely (change every {interval}s)...\n" + colors.ENDC)
    
    while not exit_flag:
        try:
            response = requests.get(url, proxies=proxy, timeout=10)
            if response.status_code == 200:
                sys.stdout.write("\r\033[K")
                elapsed = int(time() - start_time)
                change_count += 1
                print(colors.OKGREEN + f"[Change #{change_count}] IP: {response.json().get('origin')}" + 
                      colors.OKCYAN + f" | Runtime: {format_time(elapsed)}" + colors.ENDC)
        except requests.exceptions.Timeout:
            sys.stdout.write("\r\033[K")
            print(colors.WARNING + "Connection timed out. Retrying..." + colors.ENDC)
        except Exception as e:
            sys.stdout.write("\r\033[K")
            print(colors.FAIL + "An error occurred: {}".format(str(e)[:80]) + colors.ENDC)
        
        sleep_remaining = interval
        while sleep_remaining > 0 and not exit_flag:
            sleep(min(0.5, sleep_remaining))
            sleep_remaining -= 0.5
        
        if not exit_flag:
            change_ip()

if __name__ == "__main__":
    try:
        Main()
    except KeyboardInterrupt:
        print(colors.OKGREEN + "\n\nExiting cleanly. Goodbye!" + colors.ENDC)
        os._exit(0)
