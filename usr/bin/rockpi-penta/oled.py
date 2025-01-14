#!/usr/bin/env python3

"""
    Manage the display according to the configuration data and
    the state of the hardware.

    Displayed pages have their values update just prior to display
    and the user can specify a refresh period so that a page that
    stays up a long time can be refreshed to get current state.

    I/O rates are for the period since the last update for that
    device's display page, so they are continuous collections.
"""
from pickle import NONE
import time
from weakref import ref
import misc
import fan
import Adafruit_SSD1306
import multiprocessing as mp

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

font = {  # TODO make cached func
    '10': ImageFont.truetype('fonts/DejaVuSansMono-Bold.ttf', 10),
    '11': ImageFont.truetype('fonts/DejaVuSansMono-Bold.ttf', 11),
    '12': ImageFont.truetype('fonts/DejaVuSansMono-Bold.ttf', 12),
    '13': ImageFont.truetype('fonts/DejaVuSansMono-Bold.ttf', 12),
    '14': ImageFont.truetype('fonts/DejaVuSansMono-Bold.ttf', 14),
}

def disp_init():
    disp = Adafruit_SSD1306.SSD1306_128_32(rst=None, i2c_bus=3 if misc.is_rock3() else 7)
    [getattr(disp, x)() for x in ('begin', 'clear', 'display')]
    return disp

"""
    Mainline functional code to setup environment.
    manager mutable variables are used between processes.
"""
manager = mp.Manager()

refresh_time = manager.list()
refresh_time += [time.time()]

next_time = manager.list()
next_time += [time.time()]

display_lock = mp.Lock()  # lock clean display updates

"""
    Condition the display when first imported. If we have any
    problems, our exception will signal our inability to handle
    the display.
"""
misc.set_mode(23, 0)
time.sleep(0.2)
misc.set_mode(23, 1)

try:
    disp = disp_init()
except Exception:
    misc.open_pwm_i2c()
    time.sleep(0.2)
    disp = disp_init()

image = Image.new('1', (disp.width, disp.height))
draw = ImageDraw.Draw(image)


def disp_show():
    im = image.rotate(180) if misc.conf['oled']['rotate'] else image
    disp.image(im)
    disp.display()
    draw.rectangle((0, 0, disp.width, disp.height), outline=0, fill=0)


def welcome():
    with display_lock:
        draw.text((0, 0), 'ROCKPi PENTA HAT', font=font['13'], fill=255)
        draw.text((32, 16), 'Loading...', font=font['12'], fill=255)
        disp_show()
    misc.get_disk_io_rates()
    misc.get_interface_io_rates()
    time.sleep(1)

def goodbye():
    with display_lock:
        draw.text((32, 8), 'Good Bye ~', font=font['14'], fill=255)
        disp_show()
    time.sleep(2)
    with display_lock:
        disp_show()  # clear

class GeneratedPage:
    """
    A Class to hold page generators. Page generators are
    specialized to generate their specific data, current
    to the time of display.

    page_factory will return a list of page objects.

    get_page_text will return an empty Display data list
    if we have nothing to display.
    """

    @staticmethod
    def page_factory():
        """
        Return a list of page objects.
        """
        return []

    def get_page_text(self, action=False):
        """
        Return a list of Display Text for each
        of the display lines.

        If data is invalid or missing, the list is empty,
        and should be skipped.
        """
        return {'line 1', 'line 2', 'line 3'}


class General_system_info_page0(GeneratedPage):
    """Generate list of display page 0 - Uptime, CPU Temp, Host network address."""

    @staticmethod
    def page_factory():
        return [General_system_info_page0()]

    def get_page_text(self, action=False):
        return  [{'xy': (0, -2), 'text': misc.get_info('up'), 'fill': 255, 'font': font['11']},
            {'xy': (0, 10), 'text': get_cpu_temp(), 'fill': 255, 'font': font['11']},
            {'xy': (0, 21), 'text': misc.get_info('ip'), 'fill': 255, 'font': font['11']}
        ]


class General_system_info_page1 (GeneratedPage):
    """Generate the list of display page 1 - Fan speed %, CPU use, Memory Use."""

    @staticmethod
    def page_factory():
        return [General_system_info_page1()]

    def get_page_text(self, action=False):
        return [{'xy': (0, -2), 'text': 'Fan speed: ' + str(int(fan.get_dc())) + '%', 'fill': 255, 'font': font['11']},
            {'xy': (0, 10), 'text': misc.get_info('cpu'), 'fill': 255, 'font': font['11']},
            {'xy': (0, 21), 'text': misc.get_info('mem'), 'fill': 255, 'font': font['11']}
        ]


class Disk_info_page(GeneratedPage):
    """
    Generate List of 1 Disk info page. This will show the %full
    of up to the first 4 drives specified, plus the root.
    """

    @staticmethod
    def page_factory():
        return [Disk_info_page()]

    def get_page_text(self, action=False):
        k, v = misc.get_disk_used_info()
        text1 = f'Disk: {k[0]} {v[0]}'
        text2 = ''
        text3 = ''

        if len(k) >= 5:  # take first 4 if more than 3 disks
            text2 = f'{k[1]} {v[1]}  {k[2]} {v[2]}'
            text3 = f'{k[3]} {v[3]}  {k[4]} {v[4]}'
        elif len(k) == 4:
            text2 = f'{k[1]} {v[1]}  {k[2]} {v[2]}'
            text3 = f'{k[3]} {v[3]}'
        elif len(k) == 3:
            text2 = f'{k[1]} {v[1]}  {k[2]} {v[2]}'
        elif len(k) == 2:
            text2 = f'{k[1]} {v[1]}'
        return [
                {'xy': (0, -2), 'text': text1, 'fill': 255, 'font': font['11']},
                {'xy': (0, 10), 'text': text2, 'fill': 255, 'font': font['11']},
                {'xy': (0, 21), 'text': text3, 'fill': 255, 'font': font['11']},
            ]

class Interface_io_page(GeneratedPage):
    """
    The generator for a list of display pages, one for each network
    interface whose I/O rate has been requested. The list is empty if no
    interfaces have had their I/O rates requested.
    """

    # A page object is generated for each interface.
    def __init__(self, interface_name):
        self.interface_name = interface_name

    @staticmethod
    def page_factory():
        interface_list = []
        interfaces = misc.get_interface_list()

        if not interfaces:
            return interface_list

        for interface in interfaces:
            interface_list += [Interface_io_page(interface)]
        return interface_list

    def get_page_text(self, action=False):
        # update the current rate
        interface_rate = misc.get_interface_io_rate(self.interface_name)
        rx = f'Rx:{interface_rate["rx"]:10.6f} MB/s'
        tx = f'Tx:{interface_rate["tx"]:10.6f} MB/s'
        return [
            {'xy': (0, -2), 'text': 'Network (' + self.interface_name + '):', 'fill': 255, 'font': font['11']},
            {'xy': (0, 10), 'text': rx, 'fill': 255, 'font': font['11']},
            {'xy': (0, 21), 'text': tx, 'fill': 255, 'font': font['11']}
        ]


class DiskIOPage(GeneratedPage):
    """
    The generator for a list of display pages, one for each disk
    whose I/O rate has been requested. The list is empty if no disks
    have had their I/O rates requested.
    """

    # A page object is generated for each disk.
    def __init__(self, disk_name, zpool=False):
        self.disk_name = disk_name
        self.zpool = zpool

    @staticmethod
    def page_factory():
        disk_list = []
        disks = misc.get_disk_list('io_usage_mnt_points')
        zpools = misc.get_zpools().keys() if misc.conf['disk']['zfs'] else []

        if not disks and not zpools:
            return disk_list

        for disk_name in disks:
            disk_name = misc.delete_disk_partition_number(disk_name)
            disk_list += [DiskIOPage(disk_name)]
        for disk_name in zpools:
            disk_list += [DiskIOPage(disk_name, zpool=True)]
        return disk_list

    def get_page_text(self, action=False):
        disk_rate = misc.get_zpool_io_rate(self.disk_name, skip=action) if self.zpool else misc.get_disk_io_rate(self.disk_name)
        read =  f'R:{disk_rate["rx"]:11.6f} MB/s'
        write = f'W:{disk_rate["tx"]:11.6f} MB/s'

        return [
            {'xy': (0, -2), 'text': ('Zpool' if self.zpool else 'Disk') + ' (' + self.disk_name + '):', 'fill': 255, 'font': font['11']},
            {'xy': (0, 10), 'text': read, 'fill': 255, 'font': font['11']},
            {'xy': (0, 21), 'text': write, 'fill': 255, 'font': font['11']}
        ]


class Disk_temp_info_page(GeneratedPage):
    """
    The generator for a list of 1 display page, for the temperatures
    of up to the 1st four /dev/sd* drives. The list is empty if no
    /dev/sd* disks are plugged in.
    """

    @staticmethod
    def page_factory():
        return [Disk_temp_info_page()] if misc.conf['disk']['disks_temp'] else []


    def get_page_text(self, action=False):
        """ Get the display text list of display records for this entry."""
        k, v = misc.get_disk_temp_info()
        self.k = k

        text1 = 'Disk Temps:'
        text2 = ''
        text3 = ''
        if len(k) >= 4:
            text2 = f'{k[0]} {v[0]}  {k[1]} {v[1]}'
            text3 = f'{k[2]} {v[2]}  {k[3]} {v[3]}'
        elif len(k) == 3:
            text2 = f'{k[0]} {v[0]}  {k[1]} {v[1]}'
            text3 = f'{k[2]} {v[2]}'
        elif len(k) == 2:
            text2 = f'{k[0]} {v[0]}  {k[1]} {v[1]}'
        elif len(k) == 1:
            text2 = f'{k[0]} {v[0]}'

        return [
            {'xy': (0, -2), 'text': text1, 'fill': 255, 'font': font['11']},
            {'xy': (0, 10), 'text': text2, 'fill': 255, 'font': font['11']},
            {'xy': (0, 21), 'text': text3, 'fill': 255, 'font': font['11']},
        ]


def gen_display_pages_list():
    """
    Generate all the display page objects. We will iterate through the
    list and generate their text just before display. If a generator is
    configured to not generate any page its returned list will be empty.
    """
    display_page_list = General_system_info_page0.page_factory()
    display_page_list += General_system_info_page1.page_factory()
    display_page_list += Disk_info_page.page_factory()
    display_page_list += Interface_io_page.page_factory()
    display_page_list += DiskIOPage.page_factory()
    display_page_list += Disk_temp_info_page.page_factory()
    return display_page_list


def get_cpu_temp():
    """
    Return a string with the current CPU temperature converted
    into the desired scale (f/c), ready for display
    """
    t = float(misc.get_info('temp')) / 1000
    return (
        f"CPU Temp: {t * 1.8 + 32:.0f}°F"
        if misc.is_temp_farenheit()
        else f"CPU Temp: {t:.1f}°C".format(t)
    )


def auto_slider(display_queue):
    """
    Update the display on a timed basis, if we are configured as auto.
    """
    next_time[0] = time.time() + 10
    display_queue.put(True)             # force an initial display
    while misc.conf['slider']['auto']:  # to allow retry on duration config
        if duration := misc.get_slider_sleep_duration():
            next_time[0] = time.time() + duration
            while time.time() < next_time[0]:
                time.sleep(0.1)
            display_queue.put(True)
        else:
            time.sleep(0.1)     # wait for misc to startup and read config


def display_process(display_queue):
    """
    display_process runs to update the display from a Boolean on its
    display_queue. True causes it to display the next page and can
    come from the auto_slider process as it runs through the timer
    or from the button. When a next is performed, it resets the auto
    timer so that a button advance will last as long as an auto advance.
    The refresh timer is reset.

    A False means that the display is refreshed with the current page
    and its updated data. It does not change the auto timer.
    """
    last_page = [None]
    display_list = []

    misc.get_disk_io_rates()
    misc.get_interface_io_rates()

    """
        Follow the list of pages to be generated and
        displayed and generate a fresh set when exhausted.
    """

    while True:
        action = display_queue.get()            # wait for an display request
        with display_lock:
            if not len(display_list):           # refresh before first display
                display_list += gen_display_pages_list()
            if action:                   # next page and reset time
                next_time[0] = time.time() + misc.get_slider_sleep_duration()
            refresh_time[0] = time.time() + misc.get_refresh_period()

            last_page[0] = display_list[0] if action else last_page[0] # refresh displays the last page
            if last_page[0]:
                try:
                    for item in last_page[0].get_page_text(action):
                        draw.text(**item)
                except Exception as ex:
                    print(ex)
                disp_show()
            if action:
                display_list.pop(0)

def refresh_display(display_queue):
    """
    We will refresh the display status for the current page. Refresh time
    is updated by the display_process each time a page (new or current) is
    displayed.
    """
    while misc.get_refresh_period():
        if time.time() > refresh_time[0]:
            refresh_time[0] = time.time() + misc.get_refresh_period()
            display_queue.put(False)
        time.sleep(0.1)
