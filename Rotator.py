import requests
import os
import sys
import threading
import signal
from time import sleep, time
import subprocess
import re
from collections import deque

DEFAULT_TOR_PROXY = 'socks5://127.0.0.1:9050'
DEFAULT_TOR_PROXY_HTTPS = 'socks5h://127.0.0.1:9050'
DEFAULT_IP_CHECK_URL = 'https://httpbin.org/ip'
SUDO_TIMEOUT = 10
NETWORK_CMD_TIMEOUT = 3
DNS_CACHE_DURATION = 60
GATEWAY_CACHE_DURATION = 300
IP_HISTORY_SIZE = 3

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[94m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    PINK = '\033[38;5;213m'
    HACKER_GREEN = '\033[94m'
    GRAY = '\033[90m'
    WHITE = '\033[97m'

class TorRotator:
    def __init__(self, proxy_url=None, ip_check_url=None):
        self.exit_flag = threading.Event()
        self.display_lock = threading.RLock()
        self.cache_lock = threading.Lock()
        self.change_count = 0
        self.start_time = None
        self.url = ip_check_url or DEFAULT_IP_CHECK_URL
        
        proxy = proxy_url or DEFAULT_TOR_PROXY
        self.proxy = {
            'http': proxy,
            'https': DEFAULT_TOR_PROXY_HTTPS if not proxy_url else proxy
        }
        
        self.interface = None
        self.ip_history = deque(maxlen=IP_HISTORY_SIZE)
        self._gateway_cache = None
        self._gateway_cache_time = 0
        self._dns_cache = None
        self._dns_cache_time = 0
        self._last_display_height = 0
        self._display_active = False
        self._is_changing = False
        self._current_ip = None
        self._last_ip_check = 0
        self._network_cache = {}
        self._network_cache_time = 0

    def clear_terminal(self):
        os.system('clear')

    def signal_handler(self, sig, frame):
        with self.display_lock:
            self._display_active = False
        
        sleep(0.15)
        
        with self.display_lock:
            self._clear_display_area()
            print(f"\n{Colors.PINK}{Colors.BOLD}Exit? {Colors.ENDC}", end="", flush=True)
        
        try:
            confirm = input(f"{Colors.GRAY}(y/n): {Colors.ENDC}").lower().strip()
            if confirm in ['y', 'yes']:
                self.cleanup_exit()
            else:
                print(f"{Colors.PINK}Resuming...\n{Colors.ENDC}")
                sleep(1)
                self.restart_program()
        except (EOFError, KeyboardInterrupt):
            self.cleanup_exit()

    def cleanup_exit(self):
        with self.display_lock:
            self._display_active = False
        
        with self.display_lock:
            self._clear_display_area()
            if self.start_time:
                elapsed = int(time() - self.start_time)
                print(f"\n{Colors.PINK}{'═' * 60}{Colors.ENDC}")
                print(f"{Colors.PINK}{Colors.BOLD}SESSION SUMMARY{Colors.ENDC}")
                print(f"{Colors.PINK}{'─' * 60}{Colors.ENDC}")
                print(f"{Colors.GRAY}Runtime:{Colors.ENDC} {Colors.PINK}{self.format_time(elapsed)}{Colors.ENDC}")
                print(f"{Colors.GRAY}Total Changes:{Colors.ENDC} {Colors.PINK}{self.change_count}{Colors.ENDC}")
                if self.ip_history:
                    print(f"{Colors.GRAY}Unique IPs:{Colors.ENDC} {Colors.PINK}{len(set(self.ip_history))}{Colors.ENDC}")
                print(f"{Colors.PINK}{'═' * 60}{Colors.ENDC}")
            print(f"{Colors.OKCYAN}\n✓ Exited cleanly{Colors.ENDC}")
        
        sys.exit(0)

    def restart_program(self):
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def _clear_display_area(self):
        if self._last_display_height > 0:
            for _ in range(self._last_display_height):
                sys.stdout.write('\033[A\033[2K')
            sys.stdout.write('\r')
            sys.stdout.flush()
            self._last_display_height = 0

    def _run_command(self, cmd, timeout=NETWORK_CMD_TIMEOUT, check=False):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=check
            )
            return result
        except subprocess.TimeoutExpired:
            return None
        except FileNotFoundError:
            return None
        except subprocess.CalledProcessError as e:
            return e
        except Exception:
            return None

    def get_signal_strength(self):
        if not self.interface:
            return None
        
        result = self._run_command(['iwconfig', self.interface])
        if not result:
            return None
        
        match = re.search(r'Signal level=(-?\d+) dBm', result.stdout)
        if match:
            return int(match.group(1))
        
        match = re.search(r'Link Quality=(\d+)/(\d+)', result.stdout)
        if match:
            quality = int(match.group(1))
            max_quality = int(match.group(2))
            if max_quality > 0:
                percentage = (quality / max_quality) * 100
                return int(-100 + (percentage / 100) * 50)
        
        return None

    def get_signal_bar(self, dbm):
        if dbm is None:
            return f"{Colors.GRAY}{'─' * 20} N/A{Colors.ENDC}"
        
        if dbm >= -30:
            percentage = 100
        elif dbm <= -90:
            percentage = 0
        else:
            percentage = int(((dbm + 90) / 60) * 100)
        
        if dbm >= -50:
            color = Colors.OKGREEN
        elif dbm >= -60:
            color = Colors.OKCYAN
        elif dbm >= -70:
            color = Colors.WARNING
        else:
            color = Colors.FAIL
        
        filled = int(percentage / 5)
        bar = "█" * filled + "░" * (20 - filled)
        
        return f"{color}{bar}{Colors.ENDC} {color}{percentage}%{Colors.ENDC} {Colors.GRAY}({dbm}dBm){Colors.ENDC}"

    def get_network_details(self):
        current_time = time()
        
        if self._network_cache and (current_time - self._network_cache_time) < 10:
            return self._network_cache
        
        details = {}
        
        if not self.interface:
            return details
        
        result = self._run_command(['ip', 'addr', 'show', self.interface])
        if result:
            ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', result.stdout)
            if ip_match:
                details['local_ip'] = ip_match.group(1)
            
            mac_match = re.search(r'link/ether ([0-9a-f:]+)', result.stdout)
            if mac_match:
                details['mac'] = mac_match.group(1)
        
        result = self._run_command(['iwconfig', self.interface])
        if result:
            ssid_match = re.search(r'ESSID:"([^"]+)"', result.stdout)
            if ssid_match:
                details['ssid'] = ssid_match.group(1)
            
            freq_match = re.search(r'Frequency:(\d+\.?\d*) GHz', result.stdout)
            if freq_match:
                details['frequency'] = freq_match.group(1)
            
            bitrate_match = re.search(r'Bit Rate[=:](\d+\.?\d*) Mb/s', result.stdout)
            if bitrate_match:
                details['bitrate'] = bitrate_match.group(1)
        
        with self.cache_lock:
            if not self._gateway_cache or (current_time - self._gateway_cache_time) > GATEWAY_CACHE_DURATION:
                result = self._run_command(['ip', 'route'])
                if result:
                    gw_match = re.search(r'default via (\d+\.\d+\.\d+\.\d+)', result.stdout)
                    if gw_match:
                        self._gateway_cache = gw_match.group(1)
                        self._gateway_cache_time = current_time
            
            if self._gateway_cache:
                details['gateway'] = self._gateway_cache
        
        self._network_cache = details
        self._network_cache_time = current_time
        
        return details

    def get_connected_wifi_interface(self):
        result = self._run_command(['iwconfig'])
        if result:
            for line in result.stdout.split('\n'):
                if line and not line.startswith(' '):
                    if 'ESSID:' in line and 'ESSID:off' not in line:
                        return line.split()[0]
        
        result = self._run_command(['nmcli', '-t', '-f', 'DEVICE,TYPE,STATE', 'device'])
        if result:
            for line in result.stdout.split('\n'):
                if 'wifi:connected' in line.lower():
                    return line.split(':')[0]
        
        return None

    def restart_interface(self):
        if not self.interface:
            return
        
        self._run_command(['sudo', 'ifconfig', self.interface, 'down'], timeout=SUDO_TIMEOUT)
        sleep(0.5)
        self._run_command(['sudo', 'ifconfig', self.interface, 'up'], timeout=SUDO_TIMEOUT)
        sleep(1.5)
        
        with self.cache_lock:
            self._gateway_cache = None
            self._gateway_cache_time = 0

    def check_tor_service(self):
        result = self._run_command(['service', 'tor', 'status'])
        
        if not result or result.returncode != 0:
            print(f"{Colors.FAIL}✗ Tor not running{Colors.ENDC}")
            self.start_tor_service()
        else:
            print(f"{Colors.OKCYAN}✓ Tor service active{Colors.ENDC}")

    def start_tor_service(self):
        print(f"{Colors.PINK}Starting Tor service...{Colors.ENDC}")
        self._run_command(['sudo', 'service', 'tor', 'start'], timeout=SUDO_TIMEOUT)
        sleep(2)
        self.clear_terminal()

    def change_ip(self):
        with self.display_lock:
            if self._is_changing:
                return
            self._is_changing = True
        
        try:
            self._run_command(['sudo', 'service', 'tor', 'reload'], timeout=SUDO_TIMEOUT)
            sleep(1)
            self.restart_interface()
            self.change_count += 1
        finally:
            with self.display_lock:
                self._is_changing = False

    def display_status(self):
        with self.display_lock:
            if not self._display_active or self._is_changing:
                return
            
            signal_dbm = self.get_signal_strength()
            signal_bar = self.get_signal_bar(signal_dbm)
            network_info = self.get_network_details()
            tor_ip = self.get_current_ip()
            elapsed = int(time() - self.start_time)
            
            self._clear_display_area()
            
            lines = []
            
            lines.append(f"{Colors.PINK}{Colors.BOLD}TOR EXIT IP{Colors.ENDC}")
            
            if tor_ip:
                if not self.ip_history or self.ip_history[-1] != tor_ip:
                    self.ip_history.append(tor_ip)
                
                lines.append(f"  {Colors.PINK}{Colors.BOLD}{tor_ip}{Colors.ENDC}")
                
                if len(self.ip_history) > 1:
                    recent_ips = list(self.ip_history)[:-1]
                    ip_boxes = [f"{Colors.GRAY}[{Colors.PINK}{ip}{Colors.GRAY}]{Colors.ENDC}" for ip in recent_ips]
                    lines.append(f"  {Colors.GRAY}History:{Colors.ENDC} {' '.join(ip_boxes)}")
            else:
                lines.append(f"  {Colors.FAIL}Unavailable{Colors.ENDC}")
            
            lines.append(f"  {Colors.GRAY}Runtime: {Colors.PINK}{self.format_time(elapsed)}{Colors.ENDC}  {Colors.GRAY}│{Colors.ENDC}  {Colors.GRAY}Changes: {Colors.PINK}{self.change_count}{Colors.ENDC}")
            lines.append(f"{Colors.PINK}{'─' * 70}{Colors.ENDC}")
            
            lines.append(f"{Colors.PINK}{Colors.BOLD}NETWORK STATUS{Colors.ENDC}")
            
            if self.interface:
                ssid = network_info.get('ssid', 'Unknown')
                lines.append(f"  {Colors.GRAY}Interface:{Colors.ENDC} {Colors.PINK}{self.interface}{Colors.ENDC}  {Colors.GRAY}│{Colors.ENDC}  {Colors.GRAY}SSID:{Colors.ENDC} {Colors.PINK}{ssid}{Colors.ENDC}")
                lines.append(f"  {Colors.GRAY}Signal:{Colors.ENDC}    {signal_bar}")
                
                freq = network_info.get('frequency', 'N/A')
                bitrate = network_info.get('bitrate', 'N/A')
                lines.append(f"  {Colors.GRAY}Speed:{Colors.ENDC}     {Colors.PINK}{bitrate} Mb/s{Colors.ENDC}  {Colors.GRAY}│{Colors.ENDC}  {Colors.GRAY}Frequency:{Colors.ENDC} {Colors.PINK}{freq} GHz{Colors.ENDC}")
                
                local_ip = network_info.get('local_ip', 'N/A')
                gateway = network_info.get('gateway', 'N/A')
                lines.append(f"  {Colors.GRAY}Local IP:{Colors.ENDC}  {Colors.PINK}{local_ip}{Colors.ENDC}")
                lines.append(f"  {Colors.GRAY}Gateway:{Colors.ENDC}   {Colors.PINK}{gateway}{Colors.ENDC}")
                
                dns_servers = self._get_dns_servers()
                if dns_servers:
                    dns_display = ', '.join(dns_servers[:2])
                    if len(dns_servers) > 2:
                        dns_display += f" +{len(dns_servers) - 2} more"
                    lines.append(f"  {Colors.GRAY}DNS:{Colors.ENDC}       {Colors.PINK}{dns_display}{Colors.ENDC}")
            else:
                lines.append(f"  {Colors.GRAY}No WiFi interface detected{Colors.ENDC}")
            
            lines.append(f"{Colors.PINK}{'═' * 70}{Colors.ENDC}")
            
            output = '\n'.join(lines)
            print(output, flush=True)
            
            self._last_display_height = len(lines)

    def _get_dns_servers(self):
        with self.cache_lock:
            current_time = time()
            if not self._dns_cache or (current_time - self._dns_cache_time) > DNS_CACHE_DURATION:
                result = self._run_command(['cat', '/etc/resolv.conf'], timeout=1)
                if result:
                    dns_servers = []
                    for line in result.stdout.split('\n'):
                        if line.strip().startswith('nameserver'):
                            parts = line.split()
                            if len(parts) >= 2:
                                dns = parts[1]
                                if dns not in dns_servers:
                                    dns_servers.append(dns)
                    self._dns_cache = dns_servers
                    self._dns_cache_time = current_time
                else:
                    self._dns_cache = []
            
            return self._dns_cache if self._dns_cache else []

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
        current_time = time()
        
        if self._current_ip and (current_time - self._last_ip_check) < 3:
            return self._current_ip
        
        try:
            response = requests.get(self.url, proxies=self.proxy, timeout=10)
            if response.status_code == 200:
                ip = response.json().get('origin')
                self._current_ip = ip
                self._last_ip_check = current_time
                return ip
        except requests.exceptions.RequestException:
            pass
        
        return self._current_ip

    def select_interface(self):
        self.interface = self.get_connected_wifi_interface()
        if self.interface:
            print(f"{Colors.OKCYAN}✓ WiFi interface: {self.interface}{Colors.ENDC}")
        else:
            print(f"{Colors.PINK}Using Tor only (no WiFi){Colors.ENDC}")

    def display_banner(self):
        self.clear_terminal()
        banner = f"""{Colors.PINK}
████████╗ ██████╗ ██████╗ 
╚══██╔══╝██╔═══██╗██╔══██╗
   ██║   ██║   ██║██████╔╝
   ██║   ██║   ██║██╔══██╗
   ██║   ╚██████╔╝██║  ██║
   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
{Colors.ENDC}{Colors.GRAY}
                Made by virtual
{Colors.ENDC}"""
        print(banner)

    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        self.display_banner()
        self.check_tor_service()
        self.select_interface()

        print(f"\n{Colors.PINK}Fetching initial IP...{Colors.ENDC}")
        self._current_ip = self.get_current_ip()
        if self._current_ip:
            self.ip_history.append(self._current_ip)
            print(f"{Colors.OKCYAN}✓ Current IP: {self._current_ip}{Colors.ENDC}\n")
        else:
            print(f"{Colors.WARNING}⚠ Could not fetch IP{Colors.ENDC}\n")

        try:
            interval_input = input(f"{Colors.PINK}{Colors.BOLD}Rotation interval (seconds): {Colors.ENDC}")
            interval = int(interval_input)
            if interval < 1:
                raise ValueError("Interval must be at least 1 second")
        except (ValueError, KeyboardInterrupt) as e:
            if isinstance(e, ValueError):
                print(f"{Colors.FAIL}Invalid interval. Please enter a positive number.{Colors.ENDC}")
            self.cleanup_exit()

        print(f"\n{Colors.PINK}{'═' * 70}{Colors.ENDC}")
        print(f"{Colors.PINK}Rotating every {Colors.PINK}{Colors.BOLD}{interval}s{Colors.ENDC}  "
              f"{Colors.GRAY}│{Colors.ENDC}  {Colors.PINK}Interface: {Colors.PINK}{Colors.BOLD}{self.interface or 'Tor only'}{Colors.ENDC}")
        print(f"{Colors.PINK}{'═' * 70}\n{Colors.ENDC}")

        self.start_time = time()
        
        with self.display_lock:
            self._display_active = True

        try:
            while not self.exit_flag.is_set():
                self.display_status()

                for i in range(interval):
                    if self.exit_flag.is_set():
                        break
                    sleep(1)
                    if i > 0 and (i % 5 == 0 or i == interval - 1):
                        self.display_status()

                if not self.exit_flag.is_set():
                    with self.display_lock:
                        self._clear_display_area()
                        print(f"{Colors.PINK}⟳{Colors.ENDC} {Colors.PINK}Changing IP...{Colors.ENDC}", flush=True)
                        self._last_display_height = 1
                    
                    self.change_ip()
                    self._current_ip = None
                    sleep(2)
        finally:
            pass

def main():
    try:
        rotator = TorRotator()
        rotator.run()
    except Exception as e:
        print(f"{Colors.FAIL}Fatal error: {e}{Colors.ENDC}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
