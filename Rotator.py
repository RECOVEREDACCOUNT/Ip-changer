import requests
import os
from time import sleep, time
import sys
import threading
import signal
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
        self.exit_flag = False
        self.spinner_active = False
        self.change_count = 0
        self.start_time = None
        self.url = "https://httpbin.org/ip"
        self.proxy = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}
        self.interface = None
        
    def clear_terminal(self):
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def signal_handler(self, sig, frame):
        self.exit_flag = True
        self.spinner_active = False
        
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()
        
        print("\n" + Colors.WARNING + "Exit requested..." + Colors.ENDC)
        
        try:
            confirm = input(Colors.BOLD + "Exit? (y/n): " + Colors.ENDC).lower().strip()
            if confirm in ['y', 'yes']:
                self.cleanup_exit()
            else:
                print(Colors.OKCYAN + "\nRestarting...\n" + Colors.ENDC)
                sleep(1)
                self.restart_program()
        except (EOFError, KeyboardInterrupt):
            self.cleanup_exit()
    
    def cleanup_exit(self):
        sys.stdout.write("\r\033[K")
        if self.start_time:
            elapsed = int(time() - self.start_time)
            print(Colors.GRAY + f"\n{'='*60}" + Colors.ENDC)
            print(Colors.OKCYAN + "Session Summary:" + Colors.ENDC)
            print(Colors.OKGREEN + f"  Total IP changes: {self.change_count}" + Colors.ENDC)
            print(Colors.OKGREEN + f"  Runtime: {self.format_time(elapsed)}" + Colors.ENDC)
            print(Colors.GRAY + f"{'='*60}" + Colors.ENDC)
        print(Colors.OKGREEN + "\nExiting cleanly. Goodbye!" + Colors.ENDC)
        os._exit(0)
    
    def restart_program(self):
        python = sys.executable
        os.execl(python, python, *sys.argv)
    
    def get_connected_wifi_interface(self):
        try:
            result = subprocess.run(['iwconfig'], capture_output=True, text=True)
            
            current_interface = None
            for line in result.stdout.split('\n'):
                if line and not line.startswith(' '):
                    parts = line.split()
                    if parts:
                        iface = parts[0]
                        if 'ESSID:' in line and 'ESSID:off' not in line:
                            current_interface = iface
                            break
            
            if not current_interface:
                result = subprocess.run(['nmcli', '-t', '-f', 'DEVICE,TYPE,STATE', 'device'], 
                                      capture_output=True, text=True)
                for line in result.stdout.split('\n'):
                    if 'wifi:connected' in line.lower():
                        parts = line.split(':')
                        if parts:
                            current_interface = parts[0]
                            break
            
            return current_interface
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
        try:
            print(Colors.OKBLUE + "\nChecking Tor..." + Colors.ENDC)
            response = os.system("service tor status > /dev/null 2>&1")
            if response != 0:
                print(Colors.FAIL + "Tor not running" + Colors.ENDC)
                self.start_tor_service()
            else:
                print(Colors.OKGREEN + "Tor is running" + Colors.ENDC)
        except Exception as e:
            print(Colors.FAIL + f"Failed to check Tor: {e}" + Colors.ENDC)
            sys.exit(1)
    
    def start_tor_service(self):
        try:
            print(Colors.BOLD + Colors.OKBLUE + "\nStarting Tor..." + Colors.ENDC)
            
            for i in range(1, 101):
                bar_length = 40
                filled = int(bar_length * i / 100)
                bar = '#' * filled + '-' * (bar_length - filled)
                sys.stdout.write(f"\r{Colors.HACKER_GREEN}[{bar}] {i}%{Colors.ENDC}")
                sys.stdout.flush()
                sleep(0.03)
            
            os.system("sudo service tor start > /dev/null 2>&1")
            print("\n" + Colors.OKGREEN + "Tor started" + Colors.ENDC)
            sleep(1)
            self.clear_terminal()
        except Exception as e:
            print(Colors.FAIL + f"\nFailed to start Tor: {e}" + Colors.ENDC)
            sys.exit(1)
    
    def change_ip(self):
        os.system("sudo service tor reload > /dev/null 2>&1")
        sleep(1)
        self.restart_interface()
    
    def spinner_effect(self):
        spinner = ['|', '/', '-', '\\']
        i = 0
        while self.spinner_active and not self.exit_flag:
            sys.stdout.write(f"\r{Colors.BOLD}Status: {Colors.OKCYAN}{spinner[i]} Waiting...{Colors.ENDC}")
            sys.stdout.flush()
            sleep(0.1)
            i = (i + 1) % len(spinner)
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()
    
    def format_time(self, seconds):
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
    
    def get_current_ip(self):
        try:
            response = requests.get(self.url, proxies=self.proxy, timeout=15)
            if response.status_code == 200:
                return response.json().get('origin')
            return None
        except requests.exceptions.Timeout:
            sys.stdout.write("\r\033[K")
            print(Colors.WARNING + "Connection timed out. Retrying..." + Colors.ENDC)
            return None
        except requests.exceptions.ProxyError:
            sys.stdout.write("\r\033[K")
            print(Colors.FAIL + "Proxy error. Check Tor connection." + Colors.ENDC)
            return None
        except Exception as e:
            sys.stdout.write("\r\033[K")
            error_msg = str(e)[:80]
            print(Colors.FAIL + f"Error: {error_msg}" + Colors.ENDC)
            return None
    
    def select_interface(self):
        self.interface = self.get_connected_wifi_interface()
        
        if self.interface:
            print(Colors.OKGREEN + f"WiFi interface: {self.interface}" + Colors.ENDC)
        else:
            print(Colors.OKCYAN + "Using Tor-only rotation" + Colors.ENDC)
    
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
        print(Colors.GRAY + " " * 20 + "Made by Virtual" + Colors.ENDC)
    
    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        
        self.display_banner()
        self.check_tor_service()
        self.select_interface()
        
        try:
            interval = int(input(Colors.WARNING + "\nChange interval (seconds): " + Colors.ENDC))
            if interval < 1:
                print(Colors.FAIL + "Interval must be at least 1 second" + Colors.ENDC)
                sys.exit(1)
        except ValueError:
            print(Colors.FAIL + "Invalid input. Please enter a number." + Colors.ENDC)
            sys.exit(1)
        except KeyboardInterrupt:
            self.cleanup_exit()
        
        print(Colors.GRAY + f"\n{'='*60}" + Colors.ENDC)
        print(Colors.OKBLUE + f"Running indefinitely - Change every {interval}s" + Colors.ENDC)
        if self.interface:
            print(Colors.OKCYAN + f"Interface: {self.interface}" + Colors.ENDC)
        print(Colors.GRAY + f"{'='*60}\n" + Colors.ENDC)
        
        self.spinner_active = True
        spinner_thread = threading.Thread(target=self.spinner_effect, daemon=True)
        spinner_thread.start()
        
        self.start_time = time()
        
        while not self.exit_flag:
            self.spinner_active = False
            ip = self.get_current_ip()
            
            if ip:
                elapsed = int(time() - self.start_time)
                self.change_count += 1
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                print(Colors.OKGREEN + f"[{timestamp}] " + 
                      Colors.BOLD + f"#{self.change_count} " + Colors.ENDC +
                      Colors.OKGREEN + f"IP: {ip} " + Colors.ENDC +
                      Colors.GRAY + f"| {self.format_time(elapsed)}" + Colors.ENDC)
            else:
                sleep(2)
            
            self.spinner_active = True
            
            sleep_remaining = interval
            while sleep_remaining > 0 and not self.exit_flag:
                sleep(min(0.5, sleep_remaining))
                sleep_remaining -= 0.5
            
            if not self.exit_flag:
                self.spinner_active = False
                sys.stdout.write(f"\r{Colors.OKCYAN}Changing IP...{Colors.ENDC}")
                sys.stdout.flush()
                self.change_ip()
                sys.stdout.write("\r\033[K")
                self.spinner_active = True

def main():
    rotator = TorRotator()
    try:
        rotator.run()
    except KeyboardInterrupt:
        rotator.cleanup_exit()

if __name__ == "__main__":
    main()
