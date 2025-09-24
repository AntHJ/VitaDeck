####################################
##  VitaDeck Reciever - by AntHJ  ##
######################################################
##                                                  ##
##  Connect to the Vita running VitaDeck with this  ##
##  tool and it will monitor incomming commands of  ##
##  shortcut keys and combos which get passed onto  ##
##  AutoHotKey so process..                         ##
##                                                  ##
##  Turn your Vita into a customisable  StreamDeck  ##
##                                                  ##
######################################################

import os
import sys
import socket
import ftplib
import time
import io
import subprocess
import threading
import PySimpleGUI as sg

# Constants
APP_DIR = os.getcwd()
VITA_IP_FILE = os.path.join('assets', 'VitaIP.txt')

def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)
logo_path = resource_path("logo.png")

# Load saved IP or fallback
def get_saved_ip_parts():
    saved_ip_parts = [''] * 4
    if os.path.exists(VITA_IP_FILE):
        try:
            with open(VITA_IP_FILE, 'r') as f:
                saved_ip = f.read().strip()
                parts = saved_ip.split('.')
                if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                    saved_ip_parts = parts
        except:
            pass
    if saved_ip_parts == [''] * 4:
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            saved_ip_parts = local_ip.split('.')[:3] + ['']
        except:
            saved_ip_parts = ['192', '168', '', '']
    return saved_ip_parts

def launch_decision_window():
    lostlayout = [
        [sg.Push(background_color='DarkRed'), sg.Text('\n Vita Deck - Connection lost.?\n', justification='center',text_color='White', background_color='DarkRed'), sg.Push(background_color='DarkRed')],
        [sg.Text('   ',background_color='DarkRed'), sg.Button('Reconnect', size=(12, 1)), sg.Button('Exit', size=(12, 1)), sg.Text('   ',background_color='DarkRed')],
        [sg.Text('',background_color='DarkRed')]
    ]
    popup_layout = [[sg.Column(lostlayout,background_color='DarkRed')]]
    decision_window = sg.Window('VitaDeck Connection error?', popup_layout, grab_anywhere=True, background_color='Red', no_titlebar=True, margins=(0, 0), modal=True, keep_on_top=True, finalize=True)

    while True:
        event, _ = decision_window.read()
        if event in (sg.WINDOW_CLOSED, 'Cancel'):
            break
        elif event == 'Reconnect':
            decision_window.close()
            launch_ip_window()
            break
        elif event == 'Exit':
            decision_window.close()
            os._exit(0)

    decision_window.close()

def listening(client_socket):
    while True:

        try:
            while True:
                response = client_socket.recv(1024)
                if not response:
                    print("Server closed the connection.")
                    break

                decoded = response.decode('utf-8')

                # Save to file
                with open(os.path.join(APP_DIR, "assets", "cmd.txt"), "w", encoding="utf-8") as f:
                    f.write(decoded)

                # Run AutoHotkey script
                subprocess.run([
                    os.path.join(APP_DIR, 'assets', 'ahk.exe'),
                    os.path.join(APP_DIR, 'assets', 'cmd.txt')
                ], shell=True)

        except (ConnectionResetError, socket.error) as e:            
            print(f"Connection error: {e}. Reconnecting...")
            client_socket.close()
            time.sleep(1)
            launch_decision_window()
            break
        finally:
            client_socket.close()
            time.sleep(1)  # Optional pause before reconnecting

def ip_connect():
    global client_socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.settimeout(5)  # Optional: timeout for quick failure
    client_socket.connect((ip_address, 5000))
    client_socket.sendall("Connected".encode('utf-8'))
    client_socket.settimeout(None)  # Reset timeout after connection
    
# GUI for IP input
def launch_ip_window():
    saved_ip_parts = get_saved_ip_parts()
    countdown_active = [False]  # Mutable flag to allow thread-safe cancellation
    countdown_text = sg.Text('', key='COUNTDOWN', text_color='Grey', justification='center')
    logo_element = sg.Image(filename=logo_path, pad=(0, 0))

    layout = [
        [sg.Push(), logo_element, sg.Push()],
        [sg.Push(), sg.HorizontalSeparator(), sg.Push()],
        [sg.Push(), sg.Text("\nEnter your Vita's IP Address:"), sg.Push()],
        [
            sg.Text('', pad=(6, 0)),
            sg.Input(default_text=saved_ip_parts[0], size=(5, 1), key='IP1', enable_events=True),
            sg.Text('.', pad=(2, 0)),
            sg.Input(default_text=saved_ip_parts[1], size=(5, 1), key='IP2', enable_events=True),
            sg.Text('.', pad=(2, 0)),
            sg.Input(default_text=saved_ip_parts[2], size=(5, 1), key='IP3', enable_events=True),
            sg.Text('.', pad=(2, 0)),
            sg.Input(default_text=saved_ip_parts[3], size=(5, 1), key='IP4', enable_events=True),
            sg.Text('', pad=(6, 0))
        ],
        [sg.Text("")],
        [sg.Push(), sg.Button('Connect', s=12), sg.Button('Cancel', s=12), sg.Push()],
        [sg.Push(),countdown_text,sg.Push()]
    ]

    ip_layout = [[sg.Column(layout)]]
    window = sg.Window('Vita IP Setup', ip_layout, grab_anywhere=True, no_titlebar=True, background_color='#015BBB', keep_on_top='true', margins=(0, 0), modal=True, finalize=True)

    def start_countdown():
        countdown_active[0] = True
        for i in range(6, 0, -1):
            if not countdown_active[0]:
                window['COUNTDOWN'].update('')
                return
            window['COUNTDOWN'].update(f'Auto connecting in . . {i}')
            time.sleep(1)
        if countdown_active[0]:
            window.write_event_value('AUTO_CONNECT', None)

    # Start countdown if IP was loaded from file
    if all(saved_ip_parts):
        threading.Thread(target=start_countdown, daemon=True).start()

    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, 'Cancel'):
            countdown_active[0] = False
            break
        elif event == 'AUTO_CONNECT':
            window['Connect'].click()
        elif event in ('IP1', 'IP2', 'IP3', 'IP4'):
            countdown_active[0] = False
            window['COUNTDOWN'].update('')
        elif event == 'Connect':
            countdown_active[0] = False
            ip_input = [values.get(f'IP{i}', '').strip() for i in range(1, 5)]
            if all(p.isdigit() and 0 <= int(p) <= 255 for p in ip_input):
                global ip_address
                ip_address = '.'.join(ip_input)
                try:
                    with open(VITA_IP_FILE, 'w') as f:
                        f.write(ip_address)
                except Exception as e:
                    sg.popup_error(f"Failed to save IP: {e}")
                    continue

                # Try to connect to the server
                try:
                    ip_connect()
                    window.close()
                    listening(client_socket)
                    break

                except socket.error:
                    
                    IPError_layout = [
                        [sg.Push(background_color='DarkRed'), sg.Text('\n      Cannot connect to your Vita.      \n\n      ▸ is Vita Deck running ?\n      ▸ is the IP entered correctly ?\n', text_color='White', background_color='DarkRed'), sg.Push(background_color='DarkRed')],
                        [sg.Push(background_color='DarkRed'), sg.Button('Continue', button_color=('Yellow','Red'), size=(12, 1)), sg.Push(background_color='DarkRed')],
                        [sg.Text('',background_color='DarkRed')]
                    ]
                    IPpopup_layout = [[sg.Column(IPError_layout,background_color='DarkRed')]]
                    decision_window = sg.Window('VitaDeck IP error?', IPpopup_layout, grab_anywhere=True, background_color='Red', no_titlebar=True, margins=(0, 0), modal=True, keep_on_top=True, finalize=True)
                    #sg.popup_error("Cannot connect to your Vita.\n\n ▸ is Vita Deck running ?\n ▸ is the IP entered correct ?\n", background_color='DarkRed', no_titlebar=True)
                    #window['COUNTDOWN'].update('')
                    
                    while True:
                        event, _ = decision_window.read()
                        if event in (sg.WINDOW_CLOSED, 'Continue'):
                            countdown_active[0] = False
                            decision_window.close()
                            window['COUNTDOWN'].update('')
                            break
                    
                    continue

    window.close()

# Run the app
if __name__ == '__main__':
    sg.theme('PythonPlus')
    launch_ip_window()
