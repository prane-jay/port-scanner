import os
import socket
import threading
import argparse
import json
import datetime
import random
from colorama import Fore, Style, init
from tqdm import tqdm 
from concurrent.futures import ThreadPoolExecutor
from scapy.all import IP, TCP, sr1, conf


conf.verb = 0
lock = threading.Lock()
width = os.get_terminal_size().columns
init(autoreset=True)


def connect_scan(host, port):

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    result = s.connect_ex((host,port))

    if result == 0:
        banner = ""

        try:
            s.send(b"HEAD  / HTTP/1.0\r\n\r\n")
            decoded_text = s.recv(1024).decode(errors="ignore")
            banner = (decoded_text.strip().split("\n"))[0]
        except (socket.timeout, OSError):
            pass

        try:
            status = socket.getservbyport(port)
        except OSError:
            status = "unknown"

        with lock:
            open_ports.append((port,status,banner))

    s.close()


def syn_scan(host, port):

   syn_packet = IP(dst = host) / TCP(dport = port, flags = "S")
   response = sr1(syn_packet, timeout = 1)

   if response is None:
       return "filtered"
   
   tcp_flag = response[TCP].flags

   if tcp_flag == "SA": #SYN-ACK - Port open
       rst = IP(dst = host) / TCP(dport = port, flags = "R")
       sr1(rst, timeout = 1)

       try:
           status = socket.getservbyport(port)
       except OSError:
           status = "unknown"
       
       with lock:
           open_ports.append((port,status,""))
           
   elif tcp_flag == "RA": #RST-ACK - Port closed
       return "closed"
   

def parse_ports(port_range):

    try:
        start, end = port_range.split("-")
        start, end = int(start), int(end)
    except ValueError:
        raise ValueError("Port range must be in the format START-END. Ex: 1-1024")
    
    if not (1<= start <= end <= 65535):
        raise ValueError("Ports must be between 1-65535 and START must be <= END")
    
    return start, end


def save_results(filepath, target, ports, mode, open_ports):
    
    data = {
        "target": target,
        "ports": ports,
        "mode": mode,
        "timestamp": datetime.datetime.now().isoformat(),
        "open_ports": [
            {"port": p, "service": s, "banner": b}
            for p, s, b in sorted(open_ports, key=lambda x: x[0])
        ]
    }

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
        
    print()
    print(f"Results saved to {filepath}\n".center(width))


def main():

    global open_ports
    open_ports = []

    parser = argparse.ArgumentParser(description="Python port scanner")
    parser.add_argument("--target", required = True, help = "Target IP or hostname")
    parser.add_argument("--ports", required = True, help = "Port range Ex: 1-1024")
    parser.add_argument("--mode", choices = ["connect", "syn"], default = "connect", help = "Scan Type")
    parser.add_argument("--threads", type = int, default = 100, help = "Number of threads (Connect mode only)")
    parser.add_argument("--output", help = "Save output to JSON file")
    args = parser.parse_args()

    start_port, end_port = parse_ports(args.ports)
    port_list = list(range(start_port, end_port + 1))
    
    print()
    print(Fore.YELLOW + f"Scanning ports on {args.target}".center(width))
    print(Fore.YELLOW + f"{'Ports':<6} : {args.ports}".center(width))
    print(Fore.YELLOW + f"{'Mode':<6} : {args.mode}".center(width))
    print()

    if args.mode == "connect":
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
                list(tqdm(executor.map(lambda p: connect_scan(args.target, p), port_list),
                        total=len(port_list),
                        desc="Scanning",
                        unit="port",
                        colour="yellow"))
                
        print()

        for port, status, banner in sorted(open_ports, key = lambda x: x[0]):
            if banner:
                print(Fore.GREEN + f"{port}/TCP {status} [OPEN] banner={banner!r}".center(width))
            else:
                print(Fore.GREEN + f"{port}/TCP {status} [OPEN]".center(width))
        

    elif args.mode == "syn":
        random.shuffle(port_list)
        for port in tqdm(port_list, desc="Scanning", unit="port", colour="yellow"):
            syn_scan(args.target, port)
        
        print()

        for port, status, _ in sorted(open_ports, key = lambda x: x[0]):
            print(Fore.GREEN + f"{port}/TCP {status} [OPEN]".center(width))

    print()
    print(Fore.CYAN + "---- Scan Complete ----".center(width))
    print()
    print(Fore.CYAN + f"{len(open_ports)} Open  |  {len(port_list) - len(open_ports)} Closed/Filtered".center(width))
    print()

    if args.output:
        save_results(args.output, args.target, args.ports, args.mode, open_ports)

if __name__ == "__main__":
    main()
