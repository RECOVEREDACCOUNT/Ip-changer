import requests
import os
import sys
import threading
import signal
from time import sleep, time
from datetime import datetime
import subprocess

class Colors:
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
    GRAY = '\033[90m'

class TorRotator:
    def __init__(self):
        self.exit_flag = threading.Event()
        self.spinner_active = threading.Event()
        self.change_count = 0
        self.start_time = None
        self.url = "https://httpbin.org/ip"
        self.proxy = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5h://127.0.0.1:9050'}
        self.interface = None

    def clear_terminal(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def signal_handler(self, sig, frame):
        self.exit_flag.set()
        self.spinner_active.clear()
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()
        print("\n" + Colors.WARNING + "Exit requested" + Colors.ENDC)
        try:
            confirm = input(Colors.BOLD + "Exit? (y/n): " + Colors.ENDC).lower().strip()
            if confirm in ['y', 'yes']:
                self.cleanup_exit()
            else:
                print(Colors.OKCYAN + "\nRestarting\n" + Colors.ENDC)
                sleep(1)
                self.restart_program()
        except (EOFError, KeyboardInterrupt):
            self.cleanup_exit()
        finally:
            self.spinner_active.set()

    def cleanup_exit(self):
        sys.stdout.write("\r\033[K")
        if self.start_time:
            elapsed = int(time() - self.start_time)
            print(Colors.GRAY + f"\n{'='*60}" + Colors.ENDC)
            print(Colors.OKCYAN + "Session Summary:" + Colors.ENDC)
            print(Colors.OKGREEN + f"  Runtime: {self.format_time(elapsed)}" + Colors.ENDC)
            print(Colors.GRAY + f"{'='*60}" + Colors.ENDC)
        print(Colors.OKGREEN + "\nExiting" + Colors.ENDC)
        os._exit(0)

    def restart_program(self):
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def get_connected_wifi_interface(self):
        try:
            result = subprocess.run(['iwconfig'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if line and not line.startswith(' '):
                    if 'ESSID:' in line and 'ESSID:off' not in line:
                        return line.split()[0]
            result = subprocess.run(['nmcli', '-t', '-f', 'DEVICE,TYPE,STATE', 'device'],
                                    capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'wifi:connected' in line.lower():
                    return line.split(':')[0]
        except Exception:
            return None

    def restart_interface(self):
        if not self.interface:
            return
        try:
            os.system(f"sudo ifconfig {self.interface} down > /dev/null 2>&1")
            sleep(1)
            os.system(f"sudo ifconfig {self.interface} up > /dev/null 2>&1")
            sleep(2)
        except Exception as e:
            print(Colors.WARNING + f"Failed to restart interface: {e}" + Colors.ENDC)

    def check_tor_service(self):
        if os.system("service tor status > /dev/null 2>&1") != 0:
            print(Colors.FAIL + "Tor not running, starting" + Colors.ENDC)
            self.start_tor_service()
        else:
            print(Colors.OKGREEN + "Tor is running" + Colors.ENDC)

    def start_tor_service(self):
        print(Colors.BOLD + Colors.OKBLUE + "\nStarting Tor" + Colors.ENDC)
        os.system("sudo service tor start > /dev/null 2>&1")
        sleep(1)
        self.clear_terminal()

    def change_ip(self):
        os.system("sudo service tor reload > /dev/null 2>&1")
        sleep(1)
        self.restart_interface()

    def spinner_effect(self):
        spinner = ['|', '/', '-', '\\']
        i = 0
        while not self.exit_flag.is_set():
            self.spinner_active.wait()
            sys.stdout.write(f"\r{Colors.BOLD}Status: {Colors.OKCYAN}{spinner[i]} Waiting{Colors.ENDC}")
            sys.stdout.flush()
            sleep(0.1)
            i = (i + 1) % len(spinner)
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    def safe_print_line(self, message, color=Colors.OKCYAN):
        self.spinner_active.clear()
        sys.stdout.write("\r\033[K")
        print(color + message + Colors.ENDC)
        self.spinner_active.set()

    def format_time(self, seconds):
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            mins, secs = divmod(seconds, 60)
            return f"{mins}m {secs}s" if secs else f"{mins}m"
        else:
            hours, rem = divmod(seconds, 3600)
            mins = rem // 60
            return f"{hours}h {mins}m" if mins else f"{hours}h"

    def get_current_ip(self):
        try:
            response = requests.get(self.url, proxies=self.proxy, timeout=15)
            if response.status_code == 200:
                return response.json().get('origin')
        except requests.exceptions.RequestException:
            pass
        return None

    def select_interface(self):
        self.interface = self.get_connected_wifi_interface()
        if self.interface:
            print(Colors.OKGREEN + f"WiFi interface: {self.interface}" + Colors.ENDC)
        else:
            print(Colors.OKCYAN + "Using Tor only" + Colors.ENDC)

    def display_banner(self):
        self.clear_terminal()
        print(Colors.PINK + """
████████╗ ██████╗ ██████╗        ░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░
╚══██╔══╝██╔═══██╗██╔══██╗       ░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░
   ██║   ██║   ██║██████╔╝       ░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░
   ██║   ██║   ██║██╔══██╗       ░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░
   ██║   ╚██████╔╝██║  ██║       ░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░
   ╚═╝    ╚═════╝ ╚═╝  ╚═╝        ░▒▓███████▓▒░░▒▓███████▓▒░░▒▓█▓▒░
""" + Colors.ENDC)
        print(Colors.OKCYAN + "Made by virtual" + Colors.ENDC)

    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        self.display_banner()
        self.check_tor_service()
        self.select_interface()

        try:
            interval = int(input(Colors.WARNING + "\nChange interval (seconds): " + Colors.ENDC))
            if interval < 1:
                raise ValueError
        except (ValueError, KeyboardInterrupt):
            self.cleanup_exit()

        print(Colors.GRAY + f"\n{'='*60}" + Colors.ENDC)
        print(Colors.OKBLUE + f"Running indefinitely - Change every {interval}s" + Colors.ENDC)
        if self.interface:
            print(Colors.OKCYAN + f"Interface: {self.interface}" + Colors.ENDC)
        print(Colors.GRAY + f"{'='*60}\n" + Colors.ENDC)

        self.spinner_active.set()
        threading.Thread(target=self.spinner_effect, daemon=True).start()
        self.start_time = time()

        while not self.exit_flag.is_set():
            ip = self.get_current_ip()
            if ip:
                elapsed = int(time() - self.start_time)
                self.safe_print_line(f"IP: {ip} | {self.format_time(elapsed)}", Colors.OKGREEN)
            else:
                sleep(2)

            sleep_remaining = interval
            while sleep_remaining > 0 and not self.exit_flag.is_set():
                sleep(min(0.5, sleep_remaining))
                sleep_remaining -= 0.5

            if not self.exit_flag.is_set():
                self.safe_print_line("Changing IP", Colors.OKCYAN)
                self.change_ip()

def main():
    rotator = TorRotator()
    rotator.run()

if __name__ == "__main__":
    main()
