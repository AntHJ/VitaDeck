########################################
##  VitaDeck Configurator - by AntHJ  ##
######################################################
##                                                  ##
##  Connect to the Vita running VitaDeck with this  ##
##  tool and you can create various combo buttons   ##
##  links and hotkeys for your favourite apps and   ##
##  games.. commands / key presses are sent to the  ##
##  AutoHotKey application.                         ##
##                                                  ##
##  Turn your Vita into a customisable  StreamDeck  ##
##                                                  ##
######################################################

import PySimpleGUI as sg
import os
import time
import shutil
import socket
import ftplib
import subprocess
import webbrowser
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageColor
import glob
import io
sg.theme('PythonPlus')

# Constants
WINDOW_SIZE = (960, 644)
GRID_ROWS = 3
GRID_COLS = 5
SQUARE_SIZE = (144, 144)
IMAGE_KEYS = [f'IMG_{i+1}' for i in range(GRID_ROWS * GRID_COLS)]
page_cache = {i: [None] * len(IMAGE_KEYS) for i in range(1, 11)}
TEMP_DIR = 'assets/temp'
KEYSETS_DIR = 'KeySets'
PAGES_DIR = 'SinglePages'
# Ensure base directories exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(KEYSETS_DIR, exist_ok=True)

APP_DIR = os.getcwd()
VITA_IP_FILE = os.path.join('assets', 'VitaIP.txt')
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

def is_valid_color(color_str):
    try:
        ImageColor.getrgb(color_str)
        return True
    except ValueError:
        return False

def load_page_data(page_number):
    page_dir = os.path.join(TEMP_DIR, str(page_number))
    os.makedirs(page_dir, exist_ok=True)
    images = []
    for i in range(len(IMAGE_KEYS)):
        img_path = os.path.join(page_dir, f'key{str(i+1).zfill(2)}.png')
        if os.path.exists(img_path):
            try:
                img = Image.open(img_path).resize(SQUARE_SIZE)
                bio = io.BytesIO()
                img.save(bio, format='PNG')
                images.append(bio.getvalue())
            except:
                images.append(None)
        else:
            images.append(None)
    return images

# Helper to create blank image
def blank_image():
    img = Image.new('RGB', SQUARE_SIZE, color='black')
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    return bio.getvalue()

# Create grid layout
def create_grid(images):
    grid = []
    idx = 0
    for _ in range(GRID_ROWS):
        row = []
        for _ in range(GRID_COLS):
            img_data = images[idx] if images[idx] else blank_image()
            row.append(sg.Button(image_data=img_data, key=IMAGE_KEYS[idx], border_width=1, button_color=('lightgray', 'black'), pad=(5, 5)))
            idx += 1
        grid.append(row)
    return grid

# Preview cropping window
def open_preview_window(image_path, update_callback):
    canvas_size = (300, 300)
    frame_size = 145
    zoom = 1.0
    dragging = False
    offset_x = 0
    offset_y = 0
    move_x = 0
    move_y = 0
    rotation = 0
    tk_img = None

    original = Image.open(image_path).convert('RGB')
    frame_x = (canvas_size[0] - frame_size) // 2
    frame_y = (canvas_size[1] - frame_size) // 2

    def get_transformed_image():
        scaled = original.resize((int(original.width * zoom), int(original.height * zoom)))
        rotated = scaled.rotate(rotation, expand=True)
        canvas_img = Image.new('RGB', canvas_size, color='black')
        x = (canvas_size[0] - rotated.width) // 2 + move_x
        y = (canvas_size[1] - rotated.height) // 2 + move_y
        canvas_img.paste(rotated, (x, y))
        return canvas_img, x, y, rotated

    def draw_canvas():
        nonlocal tk_img
        img, x_offset, y_offset, transformed = get_transformed_image()

        # Create RGBA canvas and paste the transformed image
        canvas_img = Image.new('RGBA', canvas_size, (0, 0, 0, 255))
        canvas_img.paste(transformed.convert('RGBA'), (x_offset, y_offset))

        # Create overlay with transparent base
        overlay = Image.new('RGBA', canvas_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Define black with opacity
        blk_transparent = (15, 15, 15, 200)

        # Draw top overlay
        draw.rectangle([0, 0, canvas_size[0], frame_y], fill=blk_transparent)

        # Draw bottom overlay
        draw.rectangle([0, frame_y + frame_size, canvas_size[0], canvas_size[1]], fill=blk_transparent)

        # Draw left overlay
        draw.rectangle([0, frame_y, frame_x, frame_y + frame_size], fill=blk_transparent)

        # Draw right overlay
        draw.rectangle([frame_x + frame_size, frame_y, canvas_size[0], frame_y + frame_size], fill=blk_transparent)

        # Composite overlay on top of image
        final_img = Image.alpha_composite(canvas_img, overlay)

        # Convert to Tkinter-compatible format
        bio = io.BytesIO()
        final_img.save(bio, format='PNG')
        bio.seek(0)
        tk_img = ImageTk.PhotoImage(Image.open(bio))

        canvas.delete("IMG")
        canvas.create_image(0, 0, anchor='nw', image=tk_img, tags="IMG")

        canvas.delete("FRAME")
        canvas.create_rectangle(frame_x, frame_y, frame_x + frame_size, frame_y + frame_size,
                                outline='red', width=2, tags="FRAME")

        return x_offset, y_offset


    layoutA = [
        [sg.Canvas(key='CANVAS', size=canvas_size, background_color='black')],
        [sg.Image(key='PREVIEW')],
        [sg.Push(),sg.Button('-', s=3), sg.Slider(range=(0.01, 4.00), resolution=0.01, orientation='h', size=(25, 8), disable_number_display=True, default_value=1.0, key='ZOOM', enable_events=True), sg.Button('+', s=3),sg.Push()],
]

    layoutB =[
        # D-pad and zoom/reset controls
        [sg.Text('\n')],
        [sg.Text('Zoom :',justification='Right',s=10),sg.Push(),sg.Text('',key='ZOOM_TEXT'),sg.Push()],
        [sg.Text('X Position :',justification='Right',s=10),sg.Push(),sg.Text('',key='X_POS_TEXT'),sg.Push()],
        [sg.Text('Y Position :',justification='Right',s=10),sg.Push(),sg.Text('',key='Y_POS_TEXT'),sg.Push()],
        [sg.Text('')],
        [sg.Push(),
         sg.Column([
             [sg.Push(), sg.Button('/\\', s=3), sg.Push()],
             [sg.Button('<', s=3), sg.Text('', size=(3, 1)), sg.Button('>', s=3)],
             [sg.Push(), sg.Button('\\/', s=3), sg.Push()]
         ]),
         
         sg.Column([
             #[sg.Button('+', s=3)],
             #[sg.Button('-', s=3)]
         ]),
         sg.Push(),
         sg.Button('Reset', s=6),
         sg.Push()
        ],

        [sg.Text('\n\n')],
        [sg.Push(), sg.Button('OK', s=12), sg.Button('Cancel', s=12), sg.Push()]
]

    layout = [
    [sg.Column(layoutA, element_justification='center'),sg.VerticalSeparator(),
     sg.Column(layoutB, element_justification='center')]
]

    window = sg.Window('Image Preview', layout, keep_on_top=True, finalize=True)
    canvas_elem = window['CANVAS']
    canvas = canvas_elem.TKCanvas

    x_offset, y_offset = draw_canvas()

    dragging = False
    last_x = 0
    last_y = 0

    def start_drag(event):
        nonlocal dragging, last_x, last_y
        dragging = True
        last_x = event.x
        last_y = event.y

    def do_drag(event):
        nonlocal move_x, move_y, last_x, last_y
        if dragging:
            dx = event.x - last_x
            dy = event.y - last_y
            move_x += dx
            move_y += dy
            last_x = event.x
            last_y = event.y
            window['X_POS_TEXT'].update(str(move_x))
            window['Y_POS_TEXT'].update(str(move_y))
            draw_canvas()

    def stop_drag(event):
        nonlocal dragging
        dragging = False

    canvas.bind("<ButtonPress-1>", start_drag)
    canvas.bind("<B1-Motion>", do_drag)
    canvas.bind("<ButtonRelease-1>", stop_drag)

    while True:
        window['ZOOM_TEXT'].update(f'{zoom:.2f}')
        window['X_POS_TEXT'].update(str(move_x))
        window['Y_POS_TEXT'].update(str(move_y))

        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Cancel'):
            break
        elif event == '+':
            zoom = min(zoom + 0.01, 4.0)
            window['ZOOM'].update(value=zoom)
            draw_canvas()
        elif event == '-':
            zoom = max(zoom - 0.01, 0.01)
            window['ZOOM'].update(value=zoom)
            draw_canvas()
        elif event == '/\\':
            move_y = move_y - 1
            draw_canvas()
        elif event == '\/':
            move_y = move_y + 1
            draw_canvas()
        elif event == '<':
            move_x = move_x - 1
            draw_canvas()
        elif event == '>':
            move_x = move_x + 1
            draw_canvas()
        elif event == 'Reset':
            zoom = 1.0
            move_x = 0
            move_y = 0
            window['ZOOM'].update(value=zoom)
            draw_canvas()

        elif event == 'ZOOM':
            zoom = values['ZOOM']
            draw_canvas()
        elif event == 'MOVE_X':
            move_x = int(values['MOVE_X'])
            draw_canvas()
        elif event == 'MOVE_Y':
            move_y = int(values['MOVE_Y'])
            draw_canvas()
        elif event == 'ROTATE':
            rotation = int(values['ROTATE'])
            draw_canvas()
        elif event == 'OK':
            _, x_offset, y_offset, transformed = get_transformed_image()
            crop_x = frame_x - x_offset
            crop_y = frame_y - y_offset
            crop_box = (
                crop_x,
                crop_y,
                crop_x + frame_size,
                crop_y + frame_size
            )

            try:
                cropped = transformed.crop(crop_box).resize((144, 144))
                bio = io.BytesIO()
                cropped.save(bio, format='PNG')
                update_callback(bio.getvalue())
                cropped.save(os.path.join('assets', 'temp', 'LastIMG.png'))

                bio.seek(0)
                window['PREVIEW'].update(data=bio.getvalue())
                
            except Exception as e:
                sg.popup_error(f"Cropping failed: {e}")
            break

    window.close()

def get_system_fonts():
        user_fonts_dir = os.path.join(
            "C:\\Users",
            os.environ.get("USERNAME", ""),
            "AppData\\Local\\Microsoft\\Windows\\Fonts"
        )
        font_dirs = [user_fonts_dir, f'{APP_DIR}\\assets', "C:\\Windows\\Fonts"]
        font_files = []
        for dir_path in font_dirs:
            if os.path.exists(dir_path):
                font_files.extend(glob.glob(os.path.join(dir_path, "*.ttf")))
        return {os.path.basename(f): f for f in font_files}

font_dict = get_system_fonts()
font_names = sorted(font_dict.keys())
default_settings = {
    'text': '',
    'font': font_names[0],
    'size': '30',
    'color': 'White',
    'bg_color': '-none-',
    'x': 10,
    'y': 10
}

def open_image_viewer_with_overlay(image_data, key_index):
    base_img = Image.open(io.BytesIO(image_data)).convert('RGB')

    def get_system_fonts():
        user_fonts_dir = os.path.join(
            "C:\\Users",
            os.environ.get("USERNAME", ""),
            "AppData\\Local\\Microsoft\\Windows\\Fonts"
        )
        font_dirs = [user_fonts_dir, f'{APP_DIR}\\assets', "C:\\Windows\\Fonts"]
        font_files = []
        for dir_path in font_dirs:
            if os.path.exists(dir_path):
                font_files.extend(glob.glob(os.path.join(dir_path, "*.ttf")))
        return {os.path.basename(f): f for f in font_files}

    def image_to_bytes(img):
        with io.BytesIO() as output:
            img.save(output, format="PNG")
            return output.getvalue()

    def draw_text_overlay(base_img, text, font_path, font_size, font_color, bg_color, x=10, y=10):
        # Determine base canvas
        if bg_color and bg_color.lower() != '-none-' and is_valid_color(bg_color):
            try:
                img = Image.new('RGB', base_img.size, ImageColor.getrgb(bg_color))
            except:
                img = Image.new('RGB', base_img.size, 'black')  # fallback
        else:
            img = base_img.copy()

        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception:
            font = ImageFont.load_default()

        draw.text((x, y), text, font=font, fill=font_color)
        return image_to_bytes(img)

    color_list = ['Black', 'White', 'Red', 'Green', 'Blue', 'Yellow', 'Purple', 'Orange', 'Cyan', 'Magenta', '...or type a valid HEX code']

    layoutL = [
        [sg.Slider(range=(150, -150), orientation='v', size=(7, 5), key='-Y-', default_value=default_settings['y'], enable_events=True),
         sg.Column([
             [sg.Image(data=image_data, key='-IMAGE-')],
             [sg.Slider(range=(-150, 150), orientation='h', size=(15, 5), key='-X-', default_value=default_settings['x'], enable_events=True)]
         ])
        ],
    ]
    layoutR = [
        [sg.Text('Overlay Text:'), sg.Push(), sg.Input('', key='-TEXT-', size=(27, 1), enable_events=True)],
        [sg.Text('Font:'), sg.Push(), sg.Combo(font_names, readonly=True, default_value=default_settings['font'], key='-FONT-', size=(25, 1), enable_events=True)],
        [sg.Text('Size:'), sg.Push(), sg.Combo([str(i) for i in range(1, 201)], default_value=default_settings['size'], key='-SIZE-', size=(25, 1), enable_events=True)],
        [sg.Text('Text Color:'), sg.Push(), sg.Combo(['-none-'] + color_list, default_value=default_settings['color'], key='-COLOR-', size=(25, 1), enable_events=True)],
        [sg.Text('Background Color:'), sg.Push(), sg.Combo(['-none-'] + color_list, default_value=default_settings['bg_color'], key='-BG_COLOR-', size=(25, 1), enable_events=True)],

        [sg.Text('')],
        [sg.Push(), sg.Button('Reset',s=12),sg.Text(''), sg.Button('Apply',s=12), sg.Button('Close',s=12),sg.Push()]
    ]

    layout = [[sg.Column(layoutL), sg.VerticalSeparator(), sg.Column(layoutR)]]
    window = sg.Window(f'Add text overlay : Page {active_page}, Key {key_index+1}', layout, finalize=True, keep_on_top=True)
    final_image = image_data  # Default to original
    window.force_focus()
    window['-TEXT-'].set_focus()

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Close'):
            break
        if event in ('-TEXT-', '-FONT-', '-SIZE-', '-COLOR-', '-BG_COLOR-', '-X-', '-Y-'):
            text = values['-TEXT-']
            font_file = font_dict.get(values['-FONT-'], None)
            font_size = int(values['-SIZE-'])
            font_color = values['-COLOR-']
            bg_color = values['-BG_COLOR-']

            if not is_valid_color(font_color):
                font_color = f'#{font_color}' if is_valid_color(f'#{font_color}') else 'White'

            if bg_color == '-none-' or not is_valid_color(bg_color):
                bg_color = None

            x = int(values['-X-'])
            y = int(values['-Y-'])

            final_image = draw_text_overlay(base_img, text, font_file, font_size, font_color, bg_color, x, y)
            window['-IMAGE-'].update(data=final_image)

        if event == 'Reset':
            
            window['-BG_COLOR-'].update('-none-')
            window['-TEXT-'].update('')
            window['-FONT-'].update(font_names[0])
            window['-SIZE-'].update('30')
            window['-COLOR-'].update('White')
            window['-X-'].update(10)
            window['-Y-'].update(10)
            
            text = ''
            bg_color = '-none-'
            font_file = font_dict.get(font_names[0], None)
            font_size = 30
            font_color = 'White'
            x = 10
            y = 10
            
            final_image = draw_text_overlay(base_img, text, font_file, font_size, font_color, bg_color, x, y)
            window['-IMAGE-'].update(data=final_image)
            window['-TEXT-'].set_focus()

        if event == 'Apply':
            default_settings['font'] = values['-FONT-']
            default_settings['size'] = values['-SIZE-']
            default_settings['color'] = values['-COLOR-']
            default_settings['bg_color'] = values['-BG_COLOR-']
            default_settings['x'] = values['-X-']
            default_settings['y'] = values['-Y-']
            window.close()
            return final_image  # Return the updated image

    window.close()
    return None  # If closed without pressing OK

def unwrap_run_command(cmd):
    if cmd.startswith('run "') and cmd.endswith('"'):
        inner = cmd[5:-1]
        if inner.startswith('run "') and inner.endswith('"'):
            return inner[5:-1]
        return inner
    return cmd

def unwrap_send_command(cmd):
    if cmd.startswith('send "') and cmd.endswith('"'):
        inner = cmd[6:-1]
        if inner.startswith('send "') and inner.endswith('"'):
            return inner[6:-1]
        return inner
    return cmd


def helpful_information():
    help_text = """

              📘📘📘📘📘📘📘📘📘📘📘📘📘📘📘
             📘  This app uses: AutoHotKey  📘
              📘📘📘📘📘📘📘📘📘📘📘📘📘📘📘
              
   This is only a quick guide to help get you started with
   creating custom combos. For more in depth info,  goto :

       https://www.autohotkey.com/docs/v1/lib/Send.htm



   How AutoHotKey usually works is that your commands need
   to be send in a specific format.. for example:

                    send "Hello World"
        
    this would type out the text 'Hello World' when the
    key is triggerd to do so.. 
   
   
   How ive created this config, is that you only need to
    add in the custom combo box :      Hello World


    📘   📘   📘   📘   📘   📘   📘   📘   📘   📘   📘


    To send specific commands such as Alt+Tab, there are
    a few rules that need to be followed.
    
   I have added check boxes for Ctrl, Alt, and Shift keys
   to auto assign them with the first character typed.
    
    In other words if you ticked 'Shift' and type in the
    combo box,   hello   the shift key will only be held
     for the first character, resulting in a capital H.
     
    so if in this example we wanted Alt+Tab we can check
      the Alt box and enter in the combo box    {tab}
            resulting in the Alt+Tab combo..
     
    I know this all sounds confusing but its actually not
    as difficult as it is me trying to explain this...
    
    
    📘   📘   📘   📘   📘   📘   📘   📘   📘   📘   📘
    
    
    if you wanted to manually trigger a function key then
    will need to use the reference below which shows how.

                    ^   =   Ctrl
                    +   =   Shift
                    !   =   Alt
                    #   =   Windows
                    
                    
    so if for example you wanted 'Windows key + R' to open
    the run box, you would enter in the custom combo box:
    
            #r          as # triggers the Winkey
  
   in another example if you required the combo Ctrl+Shift+M
    you would use ^ for CTRL, + for shift, then the leter m
    
          your combo box entry would be :     ^+m
          
          
    📘   📘   📘   📘   📘   📘   📘   📘   📘   📘   📘      
          
          
    Other keys can be used by referencing them directly, such
    as {tab} which was mentioned earlier. as long as they are
    within these special bracktes  { } 
    
    
   🔹 Other special Keys include:

    {Esc}      {Space}     {Backspace}     {Up}     {Down}
    {Left}     {Right}     {Home}          {End}    {PgUp}
    {PgDn}     {Ins}       {Del}           {F1-F12}
    
       
       
       so for more examples :
    
                    !{tab}   =  Alt+Tab
                    #e       =  Windows key+E
                    ^r       =  CTRL+R
                    
     but dont forget you can just tick the combo boxes to
     trigger 'Ctrl', 'Alt' and the 'Shift' key
    
    
    📘   📘   📘   📘   📘   📘   📘   📘   📘   📘   📘
    
    
    If you need to use any of the keys :    ^   +   !   #
    in the combo box, like for example you wanted to text

                   Happy Birthday! your #1
                   
    because thoes keys trigger the action buttons they will
      need to be framed with {}     for eample: Hello{!}
    

     📘     📘     📘     📘     📘     📘     📘     📘
    
   
   EXTRA NOTES : again im sorry this may sound confusing 
   but its not actually that bad once you understand.
  
   You can actually assign a whole list of commands and
   start to get creative with your combos.. especially if
   you also start using pauses in your commands...
   
   for example, if your combo box had this :
   
     #r {sleep 500} cmd {enter} {sleep 500} dir {enter}
     1  2           3   4       5           6   7
    
   The result would be :
   
      1. Windows Key + R is pressed opening the run box
      2. Wait a moment
      3. type 'cmd'
      4. Press 'Enter'
      5. Wait a moment
      6. type 'dir'
      7. press 'Enter'
                              
    This will open the Windows run box and launch the
    command prompt, then show a directory listing.
       
       
      Another example combo box entry :   ^a ^c
          Result  -   [Control + A]   *select all*
                      [Control + C]   *copy*
    
    
    📘   📘   📘   📘   📘   📘   📘   📘   📘   📘   📘            
            _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _


   For more help with AutoHotkey, visit:
       https://www.autohotkey.com/docs/v1/lib/Send.htm

"""

    layout = [
        [sg.Multiline(help_text, size=(62, 20), disabled=True, font=("Courier New", 13), background_color='Black')],
        [sg.Push(), sg.Button('Website', size=(10, 1)),sg.Button('Close', size=(10, 1)), sg.Push()]
    ]

    window = sg.Window('AutoHotKey Help', layout, location=(0, 0), modal=False)

    while True:
        event, _ = window.read()
        if event == 'Website':
            webbrowser.open('https://www.autohotkey.com/docs/v1/lib/Send.htm')
        if event in (sg.WIN_CLOSED, 'Close'):
            window.close()
            break

# Edit window
def open_edit_window(index, current_image, page_temp_dir):
    img_data = current_image if current_image else blank_image()
    updated_image = img_data
    img = Image.open(io.BytesIO(img_data))
    img.save(os.path.join('assets', 'temp', 'LastIMG.png'))
    config_path = os.path.join(page_temp_dir, f'key{str(index+1).zfill(2)}')
    checkbox_value = 0
    cmdline_value = ''

    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith('checkbox='):
                    checkbox_value = int(line.strip().split('=')[1])
                elif line.startswith('cmdline='):
                    raw_cmd = line.strip().split('=', 1)[1]

                    # Unwrap based on checkbox selection
                    if checkbox_value == 1 or checkbox_value == 5: # OPEN APP OR URL
                        if raw_cmd.startswith('run "') and raw_cmd.endswith('"'):
                            cmdline_value = raw_cmd[5:-1]
                        else:
                            cmdline_value = raw_cmd
                    elif checkbox_value == 3:  # CUSTOM_HOTKEY
                        if raw_cmd.startswith('send "') and raw_cmd.endswith('"'):
                            cmdline_value = raw_cmd[6:-1]
                        else:
                            cmdline_value = raw_cmd
                    else:
                        cmdline_value = raw_cmd

    # Interpret cmdline for Hotkey dropdown
    hotkey_label = ''
    if checkbox_value == 2:
        reverse_map = {
            'send "^x"': 'Cut',
            'send "^c"': 'Copy',
            'send "^v"': 'Paste',
            'send "^z"': 'Undo',
            'send "^y"': 'Redo',
            'send "^a"': 'Select All',
            'send "^n"': 'New',
            'send "^o"': 'Open',
            'send "^w"': 'Close',
            'send "^s"': 'Save',
            'send "^!s"': 'Save as',
            'send "^p"': 'Print',
            'send "{Volume_Up}"': 'Volume Up',
            'send "{Volume_Down}"': 'Volume Down',
            'send "{Volume_Mute}"': 'Volume Mute',
            'send "#d"': 'Show/Hide Desktop',
            'send "#."': 'Emoji picker',
            'send "#l"': 'Lock PC',
            'send "^f"': 'CTRL+F',
            'send "^r"': 'CTRL+R',
            'send "^{tab}"': 'CTRL+TAB',
            'send "!{tab}"': 'ALT+TAB',
            'send "!{f4}"': 'ALT+F4'
        }

        hotkey_label = reverse_map.get(cmdline_value, 'Cut')  # Default to 'Cut' if unknown

    open_app = checkbox_value == 1
    hotkey = checkbox_value == 2
    custom_hotkey = checkbox_value == 3
    goto_page = checkbox_value == 4
    goto_page_value = cmdline_value if goto_page else '1'
    open_url = checkbox_value == 5
    
    image_column = sg.Column([
        [sg.Image(data=img_data, key='PREVIEW')],
        [sg.Push(), sg.Button('Clear', key='CLEAR'), sg.Button('Load', key='LOAD'), sg.Button('Edit', key='EDIT'), sg.Push()]
    ], pad=(10, 10))

    control_column = sg.Column([
        [sg.Checkbox('Open Application', key='OPEN_APP', enable_events=True, size=(13, 1), default=open_app),
         sg.Input(cmdline_value if open_app else '', key='APP_PATH', size=(41, 1), disabled=not open_app),
         sg.Button('Select App', key='SELECT_APP')],
        [sg.Checkbox('Open URL', key='OPEN_URL', enable_events=True, size=(13, 1), default=open_url),
         sg.Input(cmdline_value if open_url else '', key='URL_PATH', size=(53, 1), disabled=not open_url)],
        [sg.Checkbox('Hotkey', key='HOTKEY', enable_events=True, size=(13, 1), default=hotkey),
        sg.Combo(
        ['Cut', 'Copy', 'Paste', 'Undo', 'Redo', 'Select All', ' ────────────',
         'New', 'Open', 'Close', 'Save', 'Save as', 'Print', ' ────────────',
         'Volume Up', 'Volume Down', 'Volume Mute', ' ────────────',
         'Show/Hide Desktop', 'Emoji picker', 'Lock PC',' ────────────',
         'CTRL+F', 'CTRL+R', 'CTRL+TAB', 'ALT+TAB', 'ALT+F4'],
         key='HOTKEY_LIST', readonly=True, size=(17, 1), disabled=not hotkey, default_value=hotkey_label),
         sg.Push(), sg.Button('Custom Hotkey Help', key='CUSTOM_HELP', size=(22, 1), enable_events=True)],
        [sg.Checkbox('Custom Hotkey', key='CUSTOM_HOTKEY', enable_events=True, size=(13, 1), default=custom_hotkey),
         sg.Checkbox('Ctrl', key='CHK_CTRL', default=False),
         sg.Checkbox('Alt', key='CHK_ALT', default=False),
         sg.Checkbox('Shift', key='CHK_SHIFT', default=False),
         sg.Input(cmdline_value if custom_hotkey else '', key='CUSTOM_HOTKEY_TEXT', size=(28, 1), disabled=not custom_hotkey)],
        [sg.Checkbox('Goto Page', key='GOTO_PAGE', enable_events=True, size=(13, 1), default=goto_page),
         sg.Combo([str(i) for i in range(1, 11)], key='GOTO_PAGE_LIST', readonly=True, size=(5, 1), disabled=not goto_page, default_value=goto_page_value),
         sg.Push(),
         sg.Button('Prev page', key='GOTO_PREV', size=(10, 1), disabled=not goto_page),
         sg.Button('Next page', key='GOTO_NEXT', size=(10, 1), disabled=not goto_page),
         sg.Button('First page', key='GOTO_HOME', size=(10, 1), disabled=not goto_page),sg.Push()],
        [sg.Text('', size=(1, 1))],
        [sg.Push(), sg.Button('SAVE', button_color='DarkGreen', key='SAVE', size=(12, 1)),
         sg.Button('Cancel', key='CANCEL', size=(12, 1)),
         sg.Push(),
         sg.Button('Test', key='TEST', size=(6, 1)),  # Renamed and repositioned
         sg.Button('Delete', button_color='DarkRed', key='DELETE', size=(6, 1))]
    ], pad=(10, 10))

    layout = [[image_column, control_column]]
    window = sg.Window(f'Assign key command : Page {active_page}, Key {index+1}', layout, return_keyboard_events=True, finalize=True, modal=False)

# After window is created
    if checkbox_value == 3:  # CUSTOM_HOTKEY
        raw_text = cmdline_value
        modifiers = raw_text[:3]  # Check first 3 characters
        stripped_text = raw_text

        if '^' in modifiers:
            window['CHK_CTRL'].update(value=True)
            stripped_text = stripped_text.replace('^', '', 1)
        if '!' in modifiers:
            window['CHK_ALT'].update(value=True)
            stripped_text = stripped_text.replace('!', '', 1)
        if '+' in modifiers:
            window['CHK_SHIFT'].update(value=True)
            stripped_text = stripped_text.replace('+', '', 1)

        window['CUSTOM_HOTKEY_TEXT'].update(value=stripped_text)


    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'CANCEL'):
            updated_image = None
            break
        
        elif event == 'GOTO_PREV':
            current = int(values['GOTO_PAGE_LIST'])
            new_val = str(max(1, active_page - 1))
            window['GOTO_PAGE_LIST'].update(value=new_val)

        elif event == 'GOTO_NEXT':
            current = int(values['GOTO_PAGE_LIST'])
            new_val = str(min(10, active_page + 1))
            window['GOTO_PAGE_LIST'].update(value=new_val)
            
        elif event == 'GOTO_HOME':
            current = int(values['GOTO_PAGE_LIST'])
            new_val = str(min(10, 1))
            window['GOTO_PAGE_LIST'].update(value=new_val)
            
        elif event == 'CLEAR':
            updated_image = blank_image()
            window['PREVIEW'].update(data=updated_image)
        elif event == 'LOAD':
            file_path = sg.popup_get_file('Select an image', no_window=True, file_types=(("Image Files", "*.png;*.jpg;*.bmp"),))
            if file_path:
                def update_preview(data):
                    nonlocal updated_image
                    updated_image = data
                    window['PREVIEW'].update(data=data)
                open_preview_window(file_path, update_preview)
        elif event == 'EDIT':
            last_img_path = os.path.join('assets', 'temp', 'LastIMG.png')
            if os.path.exists(last_img_path):
                try:
                    with open(last_img_path, 'rb') as f:
                        last_img_data = f.read()
                    window.Hide()
                    result = open_image_viewer_with_overlay(last_img_data, index)
                    window.UnHide()
                    if result:
                        updated_image = result
                        window['PREVIEW'].update(data=updated_image)
                except Exception as e:
                    sg.popup_error(f"❌ Failed to load LastIMG.png:\n{e}", no_titlebar=True, background_color='DarkRed')
            else:
                sg.popup_error("❌ No cropped image found.\nPlease load and crop an image first.", no_titlebar=True, background_color='DarkRed')

        elif event == 'SELECT_APP':
            default_apppath = r'C:\ProgramData\Microsoft\Windows\Start Menu\Programs'
            app_path = sg.popup_get_file(
                '',
                no_window=True,
                file_types=(("Executable Files", "*.exe;*.bat;*.sh"),),
                initial_folder=default_apppath
            )

            if app_path:
                window['APP_PATH'].update(app_path)
        elif event in ('OPEN_APP', 'OPEN_URL', 'HOTKEY', 'CUSTOM_HOTKEY', 'GOTO_PAGE'):
            for key in ['OPEN_APP', 'OPEN_URL', 'HOTKEY', 'CUSTOM_HOTKEY', 'GOTO_PAGE']:
                window[key].update(value=(key == event))
            window['APP_PATH'].update(disabled=not values['OPEN_APP'])
            window['URL_PATH'].update(disabled=not values['OPEN_URL'])
            window['HOTKEY_LIST'].update(disabled=not values['HOTKEY'])
            window['CUSTOM_HOTKEY_TEXT'].update(disabled=not values['CUSTOM_HOTKEY'])
            window['GOTO_PAGE_LIST'].update(disabled=not values['GOTO_PAGE'])
            window['GOTO_PAGE_LIST'].update(disabled=not values['GOTO_PAGE'])
            window['GOTO_PREV'].update(disabled=not values['GOTO_PAGE'])
            window['GOTO_NEXT'].update(disabled=not values['GOTO_PAGE'])
            window['GOTO_HOME'].update(disabled=not values['GOTO_PAGE'])

        elif event == 'TEST':
            countdown_layout = [
                [sg.Text('\n0000000000000000000000000000000000000000000\n', key='COUNTDOWN_TEXT', justification='center', text_color='white', background_color='green')],
                [sg.ProgressBar(8, orientation='h', size=(15, 10), key='COUNTR')],
                [sg.Button('Cancel')],
            ]

            countdown_window = sg.Window(
                '', countdown_layout,
                no_titlebar=True,
                background_color='green',
                keep_on_top=True,
                margins=(5, 5),
                finalize=True
            )

            cancelled = False
            for i in range(8, 0, -1):
                countdown_window['COUNTDOWN_TEXT'].update(f'\nTesting button in {i} seconds . . .\n')
                countdown_window['COUNTR'].UpdateBar(8 - i)
                event, _ = countdown_window.read(timeout=1000)

                if event == 'Cancel' or event == sg.WIN_CLOSED:
                    cancelled = True
                    break


            countdown_window.close()
            if not cancelled:

            # Determine which mode is selected and build the command
                test_cmd = ''
                if values['OPEN_APP']:
                    app_path = unwrap_run_command(values["APP_PATH"].strip())
                    test_cmd = f'run "{app_path}"'

                elif values['OPEN_URL']:
                    url_path = unwrap_run_command(values["URL_PATH"].strip())
                    test_cmd = f'run "{url_path}"'

                elif values['HOTKEY']:
                    hotkey_map = {
                        'Cut': 'send "^x"',
                        'Copy': 'send "^c"',
                        'Paste': 'send "^v"',
                        'Undo': 'send "^z"',
                        'Redo': 'send "^y"',
                        'Select All': 'send "^a"',
                        'New': 'send "^n"',
                        'Open': 'send "^o"',
                        'Close': 'send "^w"',
                        'Save': 'send "^s"',
                        'Save as': 'send "^!s"',
                        'Print': 'send "^p"',
                        'Volume Up': 'send "{Volume_Up}"',
                        'Volume Down': 'send "{Volume_Down}"',
                        'Volume Mute': 'send "{Volume_Mute}"',
                        'Show/Hide Desktop': 'send "#d"',
                        'Emoji picker': 'send "#."',
                        'Lock PC':'send "#l"',
                        'CTRL+F': 'send "^f"',
                        'CTRL+R': 'send "^r"',
                        'CTRL+TAB': 'send "^{tab}"',
                        'ALT+TAB': 'send "!{tab}"',
                        'ALT+F4': 'send "!{f4}"'
                    }
                    selected = values['HOTKEY_LIST']
                    test_cmd = hotkey_map.get(selected, '')

                elif values['CUSTOM_HOTKEY']:
                    hotkey_text = values['CUSTOM_HOTKEY_TEXT'].strip()
                    modifiers = ''
                    if values.get('CHK_CTRL'):
                        modifiers += '^'
                    if values.get('CHK_ALT'):
                        modifiers += '!'
                    if values.get('CHK_SHIFT'):
                        modifiers += '+'
                    full_hotkey = modifiers + hotkey_text
                    test_cmd = f'send "{full_hotkey}"'

                # Run the command if it's valid
                if test_cmd:
                    try:
                        with open(os.path.join(APP_DIR, "assets", "cmd.txt"), "w") as f:
                            f.write(f'{test_cmd}\n')

                        subprocess.run([
                            os.path.join(APP_DIR, 'assets', 'ahk.exe'),
                            os.path.join(APP_DIR, 'assets', 'cmd.txt')
                        ], shell=True)
                    except Exception as e:
                        sg.popup_error(f"❌ Failed to run test command:\n{e}", no_titlebar=True, background_color='DarkRed')
            
        elif event == 'CUSTOM_HELP':
            # Select Custom Hotkey and uncheck others
            for key in ['OPEN_APP', 'HOTKEY', 'CUSTOM_HOTKEY', 'GOTO_PAGE']:
                window[key].update(value=(key == 'CUSTOM_HOTKEY'))

            # Enable/disable relevant fields
            window['APP_PATH'].update(disabled=True)
            window['HOTKEY_LIST'].update(disabled=True)
            window['CUSTOM_HOTKEY_TEXT'].update(disabled=False)
            window['GOTO_PAGE_LIST'].update(disabled=True)
            window['GOTO_PREV'].update(disabled=True)
            window['GOTO_NEXT'].update(disabled=True)
            window['GOTO_HOME'].update(disabled=True)

            # Focus on input
            window['CUSTOM_HOTKEY_TEXT'].set_focus()

            # Open help window
            helpful_information()

        elif event == 'DELETE':
            confirm = sg.popup_yes_no('Delete selected key ?', no_titlebar='true', keep_on_top='true', background_color='DarkRed', title='Confirm Delete')
            if confirm == 'Yes':
                img_path = os.path.join(f'{config_path}.png')
                updated_image = blank_image()
                window['PREVIEW'].update(data=updated_image)
                if os.path.exists(config_path):
                    os.remove(config_path)
                if os.path.exists(img_path):
                    os.remove(img_path)
                window.close()
                #return updated_image

        elif event == 'SAVE':
            checkbox_value = 0
            cmdline_value = ''
            if values['OPEN_APP']:
                checkbox_value = 1
                app_path = unwrap_run_command(values["APP_PATH"].strip())
                cmdline_value = f'run "{app_path}"'
            
            elif values['OPEN_URL']:
                checkbox_value = 5
                url_path = unwrap_run_command(values["URL_PATH"].strip())
                cmdline_value = f'run "{url_path}"'
                
            elif values['HOTKEY']:
                checkbox_value = 2
                hotkey_map = {
                    'Cut': 'send "^x"',
                    'Copy': 'send "^c"',
                    'Paste': 'send "^v"',
                    'Undo': 'send "^z"',
                    'Redo': 'send "^y"',
                    'Select All': 'send "^a"',
                    'New': 'send "^n"',
                    'Open': 'send "^o"',
                    'Save': 'send "^s"',
                    'Print': 'send "^p"',
                    'Volume Up': 'send "{Volume_Up}"',
                    'Volume Down': 'send "{Volume_Down}"',
                    'Volume Mute': 'send "{Volume_Mute}"'
                }
                selected = values['HOTKEY_LIST']
                cmdline_value = hotkey_map.get(selected, '')

            if values['CUSTOM_HOTKEY']:
                checkbox_value = 3
                hotkey_text = values['CUSTOM_HOTKEY_TEXT'].strip()

                # Add modifiers based on checkbox states
                modifiers = ''
                if values.get('CHK_CTRL'):
                    modifiers += '^'
                if values.get('CHK_ALT'):
                    modifiers += '!'
                if values.get('CHK_SHIFT'):
                    modifiers += '+'

                full_hotkey = modifiers + hotkey_text

                # Wrap with send if not already
                if full_hotkey.startswith('send "') and full_hotkey.endswith('"'):
                    cmdline_value = full_hotkey
                else:
                    cmdline_value = f'send "{full_hotkey}"'


            elif values['GOTO_PAGE']:
                checkbox_value = 4  # New mode
                cmdline_value = values['GOTO_PAGE_LIST']

            with open(config_path, 'w') as f:
                f.write(f'checkbox={checkbox_value}\n')
                f.write(f'cmdline={cmdline_value}\n')
            break

    window.close()
    return updated_image
image_data_list = [None] * len(IMAGE_KEYS)
selected_index = None
active_page = 1  # Default to Page 1

# Page button row
page_button_row = [sg.Text('Page :', pad=((10, 5), (10, 10)))]
for i in range(10):
    color = ('white', 'green') if i == 0 else ('white', 'gray')
    page_button_row.append(
        sg.Button(str(i+1), key=f'PAGE_{i+1}', button_color=color, size=(4, 1), pad=(2, 2))
    )

# Control buttons
page_button_row.extend([
    sg.Push(),
    sg.Text(' ', pad=((10, 5), (10, 10))),
    sg.Button('Clear Page', key='CLEAR_PAGE', size=(10, 1), pad=(2, 2)),
    sg.Button('Open page', key='OPEN_PAGE', size=(10, 1)),
    sg.Button('Save page', key='SAVE_PAGE', size=(10, 1),button_color=('white', 'darkblue'))
])

layout = [
    [sg.Column([page_button_row], justification='center')],
    [sg.Column(create_grid(image_data_list), justification='center')],
    [
        sg.Column([[
            sg.Push(),
            sg.Button('Clear ALL', key='CLEAR_ALL',size=(12, 1),button_color=('yellow', 'darkred')),
            sg.Button('Open Key Set', key='OPEN',size=(12, 1)),
            sg.Button('Save Key Set', key='SAVE',button_color=('white', 'darkblue'),size=(12, 1)),
            sg.Push(),
            sg.Button('- Send to Vita -', key='SEND',size=(14, 1), button_color=('yellow', 'DarkGreen')),
            sg.Push()
        ]], justification='center', expand_x=True),
        
        sg.Column([[
            sg.Text('Page timeout :'),
            sg.Combo([str(i) for i in range(11)], key='TIMEOUT', default_value='0', size=(5, 1), enable_events=True),
            sg.Text('seconds'),
        ]], justification='right', element_justification='right', pad=(0, 0))
    ]
]

window = sg.Window('Vita Deck - key configurator : by AntHJ', layout, resizable=True, return_keyboard_events=True, finalize=True)
window['TIMEOUT'].Widget.configure(justify='center')
window['TIMEOUT'].update(disabled=True)

# Load Page 1 images immediately

page_temp_dir = os.path.join(TEMP_DIR, str(active_page))
os.makedirs(page_temp_dir, exist_ok=True)
image_data_list = []
for i in range(len(IMAGE_KEYS)):
    key_name = f'key{str(i+1).zfill(2)}'
    img_path = os.path.join(page_temp_dir, f'{key_name}.png')
    if os.path.exists(img_path):
        try:
            img = Image.open(img_path).resize(SQUARE_SIZE)
            bio = io.BytesIO()
            img.save(bio, format='PNG')
            image_data_list.append(bio.getvalue())
        except:
            image_data_list.append(None)
    else:
        image_data_list.append(None)

# Update grid with loaded images
for i, img_data in enumerate(image_data_list):
    window[IMAGE_KEYS[i]].update(image_data=img_data if img_data else blank_image())

def add_yellow_frame(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        draw = ImageDraw.Draw(img)
        thickness = 1
        for i in range(thickness):
            draw.rectangle([i, i, img.width - i - 1, img.height - i - 1], outline='yellow')
        bio = io.BytesIO()
        img.save(bio, format='PNG')
        return bio.getvalue()
    except Exception as e:
        print(f"Error adding frame: {e}")
        return image_bytes

def connect_to_server():
    while True:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((ip_address, 5000))
            client_socket.sendall("REFRESH".encode('utf-8'))
            return client_socket
        except socket.error:
            break

while True:
    event, values = window.read()
    if event == sg.WIN_CLOSED:
        break

    page_temp_dir = os.path.join(TEMP_DIR, str(active_page))
    os.makedirs(page_temp_dir, exist_ok=True)

    if event == 'OPEN_PAGE':
        default_keypath = os.path.join(APP_DIR, 'SinglePages')
        initial_folder = default_keypath if os.path.exists(default_keypath) else APP_DIR

        source_folder = sg.popup_get_folder(
            'Select folder to open page',
            no_window=True,
            initial_folder=initial_folder
        )

        if source_folder:
            confirm = sg.popup_yes_no(
                'Are you sure you want to replace the current page\nwith the selected folder?',
                no_titlebar=True,
                background_color='DarkRed'
            )

            if confirm == 'Yes':
                try:
                    # Define your app's current page folder
                    target_folder = page_temp_dir

                    # Copy all files
                    for file in os.listdir(source_folder):
                        src_path = os.path.join(source_folder, file)
                        dst_path = os.path.join(target_folder, file)
                        if os.path.isfile(src_path):
                            shutil.copy2(src_path, dst_path)

                    # Refresh GUI
                    window[f'PAGE_{active_page}'].click()

                except Exception as e:
                    sg.popup_error(f"Failed to open page: {e}")

                
    elif event == 'SAVE_PAGE':
        save_page_layout = [
            [sg.Text("")],
            [sg.Push(), sg.Text(f'Your page will be saved in : {os.getcwd()}/SinglePages/\n'), sg.Push()],
            [sg.Push(), sg.Text('Page name:', s=12, justification='r'), sg.Input(key='PAGE_NAME'), sg.Text("  "), sg.Push()],
            [sg.Text("")],
            [sg.Push(), sg.Button('OK', s=12), sg.Button('Cancel', s=12), sg.Push()],
            [sg.Text("")]
        ]

        save_page_layoutx = [[sg.Column(save_page_layout)]]
        save_page_window = sg.Window('Save Page', save_page_layoutx, no_titlebar=True, background_color='Green', keep_on_top=True, margins=(0, 0), modal=True)

        while True:
            page_event, page_values = save_page_window.read()
            if page_event in (sg.WIN_CLOSED, 'Cancel'):
                save_page_window.close()
                break
            elif page_event == 'OK':
                save_name = page_values['PAGE_NAME'].strip()
                if save_name:
                    try:
                        base_dir = os.getcwd()
                        target_folder = os.path.join(base_dir, 'SinglePages', save_name)

                        # Overwrite warning
                        if os.path.exists(target_folder):
                            response = sg.popup_yes_no(f'Page "{save_name}" already exists.\nDo you want to overwrite it?',
                                                       title='Overwrite Warning',
                                                       keep_on_top=True,
                                                       background_color='DarkRed',
                                                       no_titlebar=True)
                            if response != 'Yes':
                                continue  # Skip saving and return to input

                        os.makedirs(target_folder, exist_ok=True)

                        # Copy files
                        for file in os.listdir(page_temp_dir):
                            src_path = os.path.join(page_temp_dir, file)
                            dst_path = os.path.join(target_folder, file)
                            if os.path.isfile(src_path):
                                shutil.copy2(src_path, dst_path)

                        save_page_window.close()
                        sg.popup('Page saved successfully!', title='Success', background_color='Green', no_titlebar=True, auto_close=True, auto_close_duration=3)
                        break

                    except Exception as e:
                        sg.popup_error(f"Failed to save page: {e}")


    if event.startswith('PAGE_'):
        for i in range(10):
            window[f'PAGE_{i+1}'].update(button_color=('white', 'gray'))
        window[event].update(button_color=('white', 'green'))
        active_page = int(event.split('_')[1])

        # Update timeout field based on selected page
        timeout_path = os.path.join(TEMP_DIR, str(active_page), 'timeout')
        if active_page == 1:
            window['TIMEOUT'].update(value='0', disabled=True)
            # Optionally overwrite the file to ensure it's 0
            os.makedirs(os.path.dirname(timeout_path), exist_ok=True)
            with open(timeout_path, 'w') as f:
                f.write('0')
        else:
            window['TIMEOUT'].update(disabled=False)
            if os.path.exists(timeout_path):
                try:
                    with open(timeout_path, 'r') as f:
                        timeout_value = f.read().strip()
                        window['TIMEOUT'].update(value=timeout_value)
                except:
                    window['TIMEOUT'].update(value='0')
            else:
                window['TIMEOUT'].update(value='0')

        # Load images for selected page
        image_data_list = load_page_data(active_page)
        for i, img_data in enumerate(image_data_list):
            window[IMAGE_KEYS[i]].update(image_data=img_data if img_data else blank_image())

    elif event == 'CLEAR_PAGE':
        confirm = sg.popup_yes_no(f'Are you sure you want to clear Page {active_page}?\nThis will delete all images and configs for this page.', no_titlebar='true', keep_on_top='true', background_color='DarkRed', title='Confirm Clear Page')
        if confirm == 'Yes':
            window['TIMEOUT'].update(value='0')
            page_temp_dir = os.path.join(TEMP_DIR, str(active_page))
            os.makedirs(page_temp_dir, exist_ok=True)
            for filename in os.listdir(page_temp_dir):
                file_path = os.path.join(page_temp_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print(f"Failed to delete {file_path}: {e}")
    
            image_data_list = [None] * len(IMAGE_KEYS)
            for key in IMAGE_KEYS:
                window[key].update(image_data=blank_image(), button_color=('lightgray', 'black'))
            selected_index = None

    elif event == 'CLEAR_ALL':
        confirm = sg.popup_yes_no('Are you sure you want to clear *ALL* pages?\nThis will delete all images and configs from every page.', no_titlebar='true', keep_on_top='true', background_color='DarkRed', title='Confirm Clear All')
        if confirm == 'Yes':
            window['TIMEOUT'].update(value='0')
            for page_num in range(1, 11):
                page_dir = os.path.join(TEMP_DIR, str(page_num))
                os.makedirs(page_dir, exist_ok=True)
                
                # Delete timeout file if exists
                timeout_path = os.path.join(page_dir, 'timeout')
                if os.path.exists(timeout_path):
                    os.remove(timeout_path)
                
                for i in range(len(IMAGE_KEYS)):
                    key_name = f'key{str(i+1).zfill(2)}'
                    img_path = os.path.join(page_dir, f'{key_name}.png')
                    config_path = os.path.join(page_dir, key_name)

                    # Overwrite with blank image
                    blank = Image.new('RGB', SQUARE_SIZE, color='black')
                    blank.save(img_path)

                    # Delete config file if exists
                    if os.path.exists(config_path):
                        os.remove(config_path)

            # Reset current view
            image_data_list = [None] * len(IMAGE_KEYS)
            for key in IMAGE_KEYS:
                window[key].update(image_data=blank_image(), button_color=('lightgray', 'black'))
            selected_index = None


    elif event == 'OPEN':
        default_keypath = f'{APP_DIR}/KeySets/'
        folder = sg.popup_get_folder('', no_window=True,initial_folder=default_keypath)
        if folder:
            for page_num in range(1, 11):
                page_dir = os.path.join(folder, str(page_num))
                if not os.path.exists(page_dir):
                    continue

                images = []
                for i in range(len(IMAGE_KEYS)):
                    key_name = f'key{str(i+1).zfill(2)}'
                    img_path = os.path.join(page_dir, f'{key_name}.png')
                    config_path = os.path.join(page_dir, key_name)

                    if os.path.exists(img_path):
                        try:
                            img = Image.open(img_path).resize(SQUARE_SIZE)
                            bio = io.BytesIO()
                            img.save(bio, format='PNG')
                            images.append(bio.getvalue())
                        except:
                            images.append(None)
                    else:
                        images.append(None)

                    # Copy image and config to temp
                    temp_page_dir = os.path.join(TEMP_DIR, str(page_num))
                    os.makedirs(temp_page_dir, exist_ok=True)
                    if os.path.exists(img_path):
                        shutil.copy(img_path, os.path.join(temp_page_dir, f'{key_name}.png'))
                    if os.path.exists(config_path):
                        shutil.copy(config_path, os.path.join(temp_page_dir, key_name))

                page_cache[page_num] = images

            # Load active page into grid
            image_data_list = page_cache[active_page]
            for i, img_data in enumerate(image_data_list):
                window[IMAGE_KEYS[i]].update(image_data=img_data if img_data else blank_image())

    elif event == 'TIMEOUT':
        timeout_value = values['TIMEOUT'].strip()
        if timeout_value.isdigit() and 0 <= int(timeout_value) <= 999:
            timeout_path = os.path.join(TEMP_DIR, str(active_page), 'timeout')
            try:
                with open(timeout_path, 'w') as f:
                    f.write(timeout_value)
            except Exception as e:
                sg.popup_error(f"Failed to save timeout value:\n{e}")
        else:
            sg.popup_error("Please enter a valid number between 0 and 999.")


    elif event == 'SAVE':
        save_layout = [
            [sg.Text("")],
            [sg.Push(),sg.Text(f'Your keyset will be saved in : {APP_DIR}/KeySets/\n'),sg.Push()],
            [sg.Push(),sg.Text('Keyset name:',s=12,justification='r'), sg.Input(key='SET_NAME'), sg.Text("  "),sg.Push()],
            [sg.Text("")],
            [sg.Push(),sg.Button('OK',s=12), sg.Button('Cancel',s=12), sg.Push()],
            [sg.Text("")]
        ]
        
        save_layoutx = [[sg.Column(save_layout)]]
        save_window = sg.Window('Save Key Set', save_layoutx, no_titlebar='True', background_color='Green', keep_on_top='True', margins=(0,0), modal=True)
        
        while True:
            save_event, save_values = save_window.read()
            if save_event in (sg.WIN_CLOSED, 'Cancel'):
                save_window.close()
                break

            elif save_event == 'OK':
                set_name = save_values['SET_NAME'].strip()
                if set_name:
                    base_save_path = os.path.join(KEYSETS_DIR, set_name)

                    # Overwrite warning
                    if os.path.exists(base_save_path):
                        response = sg.popup_yes_no(f'Keyset "{set_name}" already exists.\nDo you want to overwrite it?', 
                                                   title='Overwrite Warning', 
                                                   keep_on_top=True, 
                                                   background_color='DarkRed', 
                                                   no_titlebar=True)
                        if response != 'Yes':
                            continue  # Skip saving and return to input

                    os.makedirs(base_save_path, exist_ok=True)
    
                    for page_num in range(1, 11):
                        page_dir = os.path.join(TEMP_DIR, str(page_num))
                        save_page_dir = os.path.join(base_save_path, str(page_num))
                        os.makedirs(save_page_dir, exist_ok=True)
    
                        for i in range(len(IMAGE_KEYS)):
                            key_name = f'key{str(i+1).zfill(2)}'
                            img_path = os.path.join(page_dir, f'{key_name}.png')
                            config_path = os.path.join(page_dir, key_name)
    
                            # Save image
                            if os.path.exists(img_path):
                                shutil.copy(img_path, os.path.join(save_page_dir, f'{key_name}.png'))
                            else:
                                # Save blank image if missing
                                blank = Image.new('RGB', SQUARE_SIZE, color='black')
                                blank.save(os.path.join(save_page_dir, f'{key_name}.png'))
    
                            # Save config
                            if os.path.exists(config_path):
                                shutil.copy(config_path, os.path.join(save_page_dir, key_name))
                    
                    save_window.close()
                    sg.popup('\nSaved...\n', background_color='DarkGreen', no_titlebar='True' ,auto_close=True, auto_close_duration=3)
                    break

    elif event == 'SEND':
        # Reload saved IP before opening the window
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

        # Fallback to local IP if saved IP is invalid
        if saved_ip_parts == [''] * 4:
            try:
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
                saved_ip_parts = local_ip.split('.')[:3] + ['']
            except:
                saved_ip_parts = ['192', '168', '0', '']

        send_layoutx = [
            [sg.Push(),sg.Text("\nEnter your Vita's IP Address:"),sg.Push()],
            [
                sg.Text('', pad=(6, 0)),
                sg.Input(default_text=saved_ip_parts[0], size=(5, 1), key='IP1'),
                sg.Text('.', pad=(2, 0)),
                sg.Input(default_text=saved_ip_parts[1], size=(5, 1), key='IP2'),
                sg.Text('.', pad=(2, 0)),
                sg.Input(default_text=saved_ip_parts[2], size=(5, 1), key='IP3'),
                sg.Text('.', pad=(2, 0)),
                sg.Input(default_text=saved_ip_parts[3], size=(5, 1), key='IP4'),
                sg.Text('', pad=(6, 0))
            ],
            [sg.Text("")],
            [sg.Push(),sg.Button('Send',s=12,button_color=('white','blue')), sg.Button('Cancel',s=12),sg.Push()],
            [sg.Push(),sg.Text("Dont forget to save your keyset", text_color='Grey'),sg.Push()]
        ]
        send_layout = [[sg.Column(send_layoutx)]]
       
        send_window = sg.Window('Send to Vita', send_layout, no_titlebar='True', background_color='#015BBB', margins=(0,0), modal=True)

        while True:
            send_event, send_values = send_window.read()
            if send_event in (sg.WIN_CLOSED, 'Cancel'):
                break
                
            elif send_event == 'Send':
                ip_input = [send_values.get(f'IP{i}', '').strip() for i in range(1, 5)]
                if all(part.isdigit() and 0 <= int(part) <= 255 for part in ip_input):
                    ip_address = '.'.join(ip_input)
                    try:
                        with open(VITA_IP_FILE, 'w') as f:
                            f.write(ip_address)
                    except Exception as e:
                        sg.popup_error(f"Failed to save IP: {e}")
                    #sg.popup(f'Sending to Vita at {ip_address} (functionality to be implemented)', title='Send')
                    
                    # Define remote folder and local source
                    remote_folder = 'ux0:/data/VitaDeck/Keys'
                    local_folder = os.path.join('assets', 'temp')
                    connection_check = '/eboot.bin'
                    connect_to_server()
                    try:
                        ftp = ftplib.FTP()
                        ftp.connect(ip_address, 1337, timeout=5)
                        ftp.login()

                        # Try to retrieve file (discarding data)
                        ftp.sendcmd('TYPE I')  # Binary mode
                        ftp.cwd('/')
                        ftp.cwd('ux0:/app/VITADECK0')
                        ftp.retrbinary(f'RETR eboot.bin', lambda data: None)
                        ftp.cwd('/')
                        ftp.cwd('ux0:/data/VitaDeck')
                        remote_root = 'Keys_NEW'
                        refresh_path = 'REFRESH'
                        local_root = os.path.join('assets', 'temp')

                        # Collect all files and their relative paths
                        file_list = []
                        for root, dirs, files in os.walk(local_root):
                            for file in files:
                                local_path = os.path.join(root, file)
                                rel_path = os.path.relpath(local_path, local_root).replace('\\', '/')
                                file_list.append((local_path, rel_path))

                        # Create progress bar window
                        progress_layout = [
                            [sg.Text('Uploading files to Vita...')],
                            [sg.ProgressBar(len(file_list), orientation='h', size=(40, 20), key='PROG')],
                        ]
                        progress_window = sg.Window('Progress', progress_layout, finalize=True)
                        progress_bar = progress_window['PROG']

                        try:
                            # Create root folder
                            try:
                                ftp.mkd(remote_root)
                            except ftplib.error_perm:
                                pass

                            # Upload each file
                            for i, (local_path, rel_path) in enumerate(file_list):
                                remote_path = f'{remote_root}/{rel_path}'

                                # Create remote subfolders if needed
                                remote_dir = os.path.dirname(remote_path)
                                parts = remote_dir.split('/')
                                path_accum = ''
                                for part in parts:
                                    path_accum = f'{path_accum}/{part}' if path_accum else part
                                    try:
                                        ftp.mkd(path_accum)
                                    except ftplib.error_perm:
                                        pass  # Already exists

                                # Upload file
                                try:
                                    with open(local_path, 'rb') as f:
                                        ftp.storbinary(f'STOR {remote_path}', f)
                                except Exception as e:
                                    sg.popup_error(f"❌ Failed to upload {rel_path}:\n{e}",no_titlebar='True',background_color='DarkRed')

                                # Update progress bar
                                progress_bar.UpdateBar(i + 1)
                                progress_window.refresh()

                            progress_window.close()
                            #sg.popup(f"✅ Uploaded {len(file_list)} files to your Vita\nPress OK to refresh the Vita...", title='FTP Upload',no_titlebar='True',background_color='DarkGreen')
                        except Exception as e:
                            progress_window.close()
                            sg.popup_error(f"❌ Upload process failed:\n{e}",no_titlebar='True',background_color='DarkRed')

                        try:
                            empty_file = io.BytesIO(b'')  # File-like object with no content
                            ftp.storbinary(f'STOR {refresh_path}', empty_file)
                            sg.popup(f"✅ Uploaded {len(file_list)} files to your Vita\n", title='FTP Upload',no_titlebar='True',background_color='DarkGreen')
                        except Exception as e:
                            if not 'closed' in str(e):
                                sg.popup_error(f"❌ Failed to create REFRESH file:\n{e}",no_titlebar='True',background_color='DarkRed')

                        ftp.quit()
                    except ftplib.error_perm as e:
                        if str(e).startswith('550'):
                            sg.popup_error(f"❌ Vita not found?",no_titlebar='True',background_color='DarkRed')
                        else:
                            sg.popup_error(f"FTP permission error:\n{e}",no_titlebar='True',background_color='DarkRed')
                    except Exception as e:
                        if not 'closed' in str(e):
                            sg.popup_error(f"FTP connection failed : {e}\nPlease check the IP address",no_titlebar='True',background_color='DarkRed')

                    break
                else:
                    sg.popup_error('Invalid IP address.\nEach part must be a number between 0 and 255.',no_titlebar='True',background_color='DarkRed')

        send_window.close()

    elif event in IMAGE_KEYS:
        idx = IMAGE_KEYS.index(event)

        # If no selection yet, highlight the clicked image
        if selected_index is None:
            selected_index = idx
            img_data = image_data_list[idx] if image_data_list[idx] else blank_image()
            framed_img = add_yellow_frame(img_data)
            window[IMAGE_KEYS[idx]].update(image_data=framed_img)

        # If same image clicked again, remove highlight
        elif selected_index == idx:
            img_data = image_data_list[idx] if image_data_list[idx] else blank_image()
            window[IMAGE_KEYS[idx]].update(image_data=img_data)
            window.Hide()
            result = open_edit_window(idx, image_data_list[idx], page_temp_dir)
            window.UnHide()
            if result is not None:
                image_data_list[idx] = result
                window[IMAGE_KEYS[idx]].update(image_data=result)
                img = Image.open(io.BytesIO(result))
                img.save(os.path.join(page_temp_dir, f'key{str(idx+1).zfill(2)}.png'))
            window[IMAGE_KEYS[idx]].update(button_color=('lightgray', 'black'))
            window[f'PAGE_{active_page}'].click()
            selected_index = None

        # If different image clicked, swap them
        else:
            # Swap image data
            image_data_list[selected_index], image_data_list[idx] = image_data_list[idx], image_data_list[selected_index]

            # Update buttons with swapped images
            window[IMAGE_KEYS[selected_index]].update(image_data=image_data_list[selected_index])
            window[IMAGE_KEYS[idx]].update(image_data=image_data_list[idx])

            # Swap config files
            key_a = f'key{str(selected_index+1).zfill(2)}'
            key_b = f'key{str(idx+1).zfill(2)}'
            path_a = os.path.join(page_temp_dir, key_a)
            path_b = os.path.join(page_temp_dir, key_b)
            temp_path = os.path.join(page_temp_dir, 'key_temp')

            if os.path.exists(path_a) and os.path.exists(path_b):
                os.rename(path_a, temp_path)
                os.rename(path_b, path_a)
                os.rename(temp_path, path_b)
            elif os.path.exists(path_a):
                os.rename(path_a, path_b)
            elif os.path.exists(path_b):
                os.rename(path_b, path_a)

            # Swap image files
            img_path_a = os.path.join(page_temp_dir, f'{key_a}.png')
            img_path_b = os.path.join(page_temp_dir, f'{key_b}.png')
            temp_img_path = os.path.join(page_temp_dir, 'key_temp.png')

            if os.path.exists(img_path_a) and os.path.exists(img_path_b):
                os.rename(img_path_a, temp_img_path)
                os.rename(img_path_b, img_path_a)
                os.rename(temp_img_path, img_path_b)
            elif os.path.exists(img_path_a):
                os.rename(img_path_a, img_path_b)
            elif os.path.exists(img_path_b):
                os.rename(img_path_b, img_path_a)

            # Reset selection
            selected_index = None
            window[f'PAGE_{active_page}'].click()

    elif isinstance(event, str) and (event.startswith('Delete') or event.startswith('BackSpace')):
        if selected_index is not None:
            confirm = sg.popup_yes_no('Delete selected key ?', no_titlebar='true', keep_on_top='true', background_color='DarkRed', title='Confirm Delete')
            if confirm == 'Yes':
                key_name = f'key{str(selected_index+1).zfill(2)}'

                # Remove image and config
                image_data_list[selected_index] = None
                window[IMAGE_KEYS[selected_index]].update(image_data=blank_image())

                img_path = os.path.join(page_temp_dir, f'{key_name}.png')
                config_path = os.path.join(page_temp_dir, key_name)

                if os.path.exists(img_path):
                    os.remove(img_path)
                if os.path.exists(config_path):
                    os.remove(config_path)

                selected_index = None
            elif confirm == 'No':
                # Unselect the image and restore original
                img_data = image_data_list[selected_index] if image_data_list[selected_index] else blank_image()
                window[IMAGE_KEYS[selected_index]].update(image_data=img_data)
                selected_index = None
        # If nothing is selected, do nothing

window.close()