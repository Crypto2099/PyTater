import argparse
import hashlib
import json.decoder
import logging
import os
import random
import textwrap
import zlib
from datetime import datetime

import httpx
import signal
import sys
import threading
import time

from dotenv import load_dotenv

load_dotenv()

env_miner_id = os.getenv('miner_id')

N = []
for i, n in enumerate([47, 68, 40, 40, 40, 21]):
    N.extend([i] * n)


def rgb_to_xterm(r, g, b):
    global N
    mx = max(r, g, b)
    mn = min(r, g, b)

    if (mx - mn) * (mx + mn) <= 6250:
        c = 24 - (252 - ((r + g + b) // 3)) // 10
        if 0 <= c <= 23:
            return 232 + c

    return 16 + 36 * N[r] + 6 * N[g] + N[b]


class colors:
    FAIL = '\033[91m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    OKBLUE = '\033[94m'
    HEADER = '\033[95m'
    OKCYAN = '\033[96m'

    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class TaterError:
    sync = None
    config = None
    pending = None
    submit = None
    status = None

    def __dict__(self):
        return {'config': self.config, 'sync': self.sync, 'pending': self.pending, 'submit': self.submit,
                'status': self.status}


class PyTater:

    def __init__(self, miner_id, pretty_mode, debug_mode):
        self.block_found = False
        self.valid_miner = False

        self.block_count = 0
        self.block_height = 0
        self.halving_count = 0
        self.starch_balance = 0
        self.starting_blocks = 0
        # self.new_block_count = 0

        self.last_block = None
        self.last_block_hash = None
        self.last_own_block = None
        self.last_own_block_hash = None
        self.pending_blocks = None

        self.miner_id = miner_id
        self.pretty_mode = pretty_mode
        self.debug_mode = debug_mode

        self.errors = {}

        self.run_start = datetime.now()

        self.get_status()

    def paint(self):
        print()
        self.print_head(False)
        print(" ├─────────────────┬─────────────────────────┤ ")
        self.fix_line(f" │ Miner ID        │ {self.miner_id}")
        self.print_divider()
        self.fix_line(f" │ Running         │ {colors.OKBLUE}{self.format_last_block_hash()}", True)
        self.print_divider()
        self.fix_line(f" │ Block Height    │ {self.block_height}")
        self.print_divider()
        self.fix_line(f" │ Run Time        │ {str(self.get_runtime())[:-7]}")
        self.print_divider()
        self.fix_line(f" │ New Blocks      │ {self.block_count - self.starting_blocks}")
        self.print_divider()
        self.fix_line(f" │ Lifetime Blocks │ {self.block_count}")

        have_pending = (len(self.pending_blocks or []))
        if have_pending:
            self.print_divider()
            self.fix_line(f" │ Block Accepted  │ {self.block_found}")
            self.print_divider()
            self.fix_line(f" │ Blocks Pending  │ {len(self.pending_blocks or []).__str__()}")
            print(" ├─────────────────┴─────────────────────────┤ ")
            pending_terminal_blocks = " │ "
            terminal_block_count = 0
            for block in self.pending_blocks or []:
                red = int(block['color'][1:3], 16)
                green = int(block['color'][3:5], 16)
                blue = int(block['color'][5:7], 16)
                xterm = rgb_to_xterm(red, green, blue)
                block_char = u"\u2584"
                if block['miner_id'] == self.miner_id:
                    block_char = u"\u2587"
                pending_terminal_blocks += (f"\033[38;5;{xterm}m" + block_char + f"{colors.ENDC} ")
                terminal_block_count += 1

                if terminal_block_count == 21:
                    print(pending_terminal_blocks + "│ ")
                    pending_terminal_blocks = " │ "
                    terminal_block_count = 0
            if terminal_block_count > 0:
                print(pending_terminal_blocks + ("  " * (21 - terminal_block_count)) + "│ ")

        for key, value in self.errors.items():
            if value is not None:
                PyTater.do_error(key, value)

        self.print_close()
        print()
        print(f"   {colors.OKGREEN}Press ctrl+c to stop the miner{colors.ENDC}")
        # print(self.errors)

    @staticmethod
    def clear():
        if os.name == "nt":
            os.system("cls")
        else:
            os.system("clear")

    @staticmethod
    def fix_line(text, colored=False):
        line_len = 45
        if colored:
            line_len = 50
        while len(text) < line_len:
            text += " "
        text += f"{colors.ENDC}│ "
        print(text)

    @staticmethod
    def print_undivided():
        print(" ├───────────────────────────────────────────┤ ")

    @staticmethod
    def do_error(title, message):
        PyTater.print_undivided()
        max_width = 41
        wrapped_message = textwrap.wrap(message, width=max_width)
        formatted_title = PyTater.fill(f"!!! {title.upper()} ERROR !!!", max_width, 'center')
        print(f" │ {colors.FAIL}{formatted_title}{colors.ENDC} │ ")
        for line in wrapped_message:
            formatted_line = PyTater.fill(line, max_width, 'left')
            print(f" │ {colors.FAIL}{formatted_line}{colors.ENDC} │ ")

    @staticmethod
    def fill(line, length, align='left'):
        line_pad = length - len(line)
        pre_pad = 0
        post_pad = 0
        if align == 'right':
            pre_pad = line_pad
            post_pad = 0
        elif align == 'left':
            pre_pad = 0
            post_pad = line_pad
        elif align == 'center':
            pre_pad = line_pad // 2
            post_pad = line_pad // 2 + line_pad % 2

        return f"{' ' * pre_pad}{line}{' ' * post_pad}"

    def print_head(self, is_closed=True):
        self.clear()
        print(" ┌───────────────────────────────────────────┐ ")
        self.fix_line(f" │ {colors.OKGREEN}Starch Industries", True)
        self.fix_line(f" │ {colors.OKGREEN}PyTater Miner v4.2.0", True)
        self.fix_line(" │ Created by: @abstractpotato")
        self.fix_line(" │ With help from: @adamkdean")
        if is_closed:
            self.print_close()

    @staticmethod
    def print_close():
        print(" └───────────────────────────────────────────┘ ")

    @staticmethod
    def print_divider():
        print(" ├─────────────────┼─────────────────────────┤ ")

    def format_last_block_hash(self):
        if self.last_block_hash is None:
            return 'Syncing...'
        else:
            return f"{self.last_block_hash[0:10]}...{self.last_block_hash[-10:]}"

    def get_runtime(self):
        now = datetime.now()
        return now - self.run_start

    def get_chain_config(self):
        # logging.info("Getting chain config...")
        self.errors['config'] = None
        try:
            res = httpx.get('https://starch.one/api/blockchain_config', timeout=10)
        except httpx.ReadTimeout:
            # 15639bc8e9...974951272c
            self.errors['config'] = "Could not fetch configuration!"
            if self.pretty_mode is False or self.debug_mode:
                logging.error("Timeout fetching chain config!")
            return
        try:
            response = res.json()
        except json.decoder.JSONDecodeError:
            self.errors['config'] = "Could not decode configuration!"
            return

        try:
            self.block_height = response['blockchain_size']
            self.last_block = response['last_block']
            self.last_block_hash = self.last_block['hash']
        except KeyError:
            return

        if self.pretty_mode is False or self.debug_mode:
            logging.info(
                "Block Height: {} (Hash: {}, Color: {}, Miner: {})".format(self.block_height, self.last_block['hash'],
                                                                           self.last_block['color'],
                                                                           self.last_block['miner_id']))
        return response

    def get_pending(self):
        self.errors['pending'] = None
        try:
            res = httpx.get('https://starch.one/api/pending_blocks', timeout=10)
        except httpx.ReadTimeout:
            self.errors['pending'] = "Could not fetch pending!"
            return

        try:
            response = res.json()
        except json.decoder.JSONDecodeError:
            self.errors['pending'] = f"Could not decode pending!"
            return

        try:
            if response['pending_blocks']:
                self.block_found = False
                self.pending_blocks = response['pending_blocks']
                for block in self.pending_blocks:
                    if block['miner_id'] == self.miner_id:
                        self.block_found = True
                        self.last_own_block = block
                        self.last_own_block_hash = block['previous_hash']
        except KeyError:
            return

    def get_status(self):
        self.errors['status'] = None
        if self.miner_id is None:
            return

        try:
            res = httpx.get('https://starch.one/api/miner/' + self.miner_id, timeout=10)
        except httpx.ReadTimeout:
            self.errors['status'] = "Could not fetch status"
            return

        try:
            response = res.json()
        except json.decoder.JSONDecodeError:
            self.errors['status'] = "Could not decode status"
            if self.pretty_mode is False or self.debug_mode:
                logging.error(res)
            return

        try:
            self.starch_balance = response['balance']
            self.block_count = response['blocks']
            if self.starting_blocks == 0 and response['blocks'] != 0:
                self.starting_blocks = response['blocks']
            # if self.block_count != self.starting_blocks:
            #     self.new_block_count = self.block_count - self.starting_blocks
            self.valid_miner = True
        except KeyError as e:
            self.valid_miner = False
            self.starting_blocks = 0
            self.block_count = 0
            # self.new_block_count = 0
            self.starch_balance = 0
            self.miner_id = None
            if self.pretty_mode is False or self.debug_mode:
                logging.error("Miner ID not found!")

    def sync(self, should_sync):
        if self.pretty_mode is False or self.debug_mode:
            logging.info("Booting up anticipation... Get ready for a simmering sensation.")
        while should_sync.is_set():
            start = time.time()
            self.get_status()
            self.get_pending()
            end = time.time()
            elapsed = end - start
            # logging.info("Time spent syncing: "+elapsed.__str__())
            if elapsed < 15:
                time.sleep(15 - elapsed)
            # time.sleep(12)

    # {
    #   "blockchain_size": 3714,
    #   "halving_count": 1,
    #   "last_block": {
    #     "color": "#6c72fb",
    #     "datetime": "01-13-2024:17-06-17",
    #     "hash": "f6fdb4beadb905edcc18da884877b85f84596eed850586bb29970f5f6e658878",
    #     "id": 218713,
    #     "miner_id": "1DF92481",
    #     "previous_hash": "9c360fc71d71e81ab61718c170284a2dd2b87e582cb5fbe48c6ba4921ba05208",
    #     "reward": 25000000
    #   },
    #   "rewards": 25000000
    # }
    def mine_block(self):
        if self.pretty_mode is False or self.debug_mode:
            logging.info("Unearthing $STRCH treasures with potato prowess... Mining spudtastic crypto gold.")
        self.get_chain_config()
        if self.block_found and self.last_own_block['previous_hash'] == self.last_block['hash']:
            if self.pretty_mode is False or self.debug_mode:
                logging.info("My Last Block:     (Hash: {}, Color: {})".format(self.last_own_block['previous_hash'],
                                                                               self.last_own_block['color']))
        else:
            if self.pretty_mode is False or self.debug_mode:
                logging.info("We should mine a block!")
            new_block = self.solve(self.last_block['hash'])
            self.submit_block(new_block)

    # def test_error(self):
    #     self.errors['test'] = None
    #     try:
    #         res = requests.post('https://starch.one/api/null')
    #     except:
    #         self.errors['test'] = "This is a test error! It is long!"
    #         return
    #
    #     if not res.ok:
    #         self.errors['test'] = f"{res.status_code}: {res.text}"
    #         return

    def submit_block(self, new_block):
        self.errors['submit'] = None
        try:
            httpx.post('https://starch.one/api/submit_block', json=new_block, timeout=10)
        except httpx.WriteTimeout:
            self.errors['submit'] = "Could not submit block?!"
            return

        if self.pretty_mode is False or self.debug_mode:
            logging.info("New block submitted to the chain!")

    def solve(self, blockhash):
        color = self.randomColor(blockhash)
        if self.pretty_mode is False or self.debug_mode:
            logging.debug(
                "Solving New Block:\nHash: {}\nMiner ID: {}\nColor: {}".format(blockhash, self.miner_id, color))
        solution = blockhash + " " + self.miner_id + " " + color
        m = hashlib.sha256()
        m.update(bytes(solution, 'ascii'))
        new_hash = m.hexdigest()
        if self.pretty_mode is False or self.debug_mode:
            logging.info("Block hash: {}".format(new_hash))
        return {'hash': new_hash, 'color': color, 'miner_id': self.miner_id}

    def randomColor(self, blockhash: str):
        seed = zlib.crc32(bytes(blockhash + self.miner_id, 'ascii'))
        random.seed(seed)
        random_number = random.randint(0, 16777215)
        hex_number = '{0:06X}'.format(random_number)
        return '#' + hex_number

        # return "#000000"

    def mine(self, should_mine):
        if self.pretty_mode is False or self.debug_mode:
            logging.info("Diving deep into the crypto potato mine... Extracting $STRCH gems with starchy precision.")
        while should_mine.is_set():
            start = time.time()
            self.mine_block()
            # TODO: Remove later
            # self.test_error()
            end = time.time()
            elapsed = end - start
            if elapsed < 24.5:
                time.sleep(24.5 - elapsed)


miner = None
running_sync = None
miner_running = None
do_mine = threading.Event()
run_sync = threading.Event()


def end_script(signal, frame):
    global do_mine, run_sync
    logging.info("Stop signal received!")
    do_mine.clear()
    run_sync.clear()
    sys.exit(0)


def run(miner_id, pretty_mode, debug_mode):
    global do_mine, run_sync, running_sync, miner_running, miner
    # global valid_miner, miner_id
    # if pretty_mode is False:
    logging.info("Loading potato goodness... Spudtacular moments are on the way!")

    miner = PyTater(miner_id, pretty_mode, debug_mode)

    run_sync.set()
    running_sync = threading.Thread(target=miner.sync, args=(run_sync,), daemon=True)
    running_sync.start()

    while miner.valid_miner is False:
        if env_miner_id == None:
            miner.miner_id = input("Enter your Miner ID: ")
        else:
            miner.miner_id = env_miner_id
        miner.get_status()

    do_mine.set()
    miner_running = threading.Thread(target=miner.mine, args=(do_mine,), daemon=True)
    miner_running.start()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog="PyTater", description="Python-based Starch Mining!")
    parser.add_argument("-m", "--miner_id", help="The Miner ID you wish to use", nargs="?")
    parser.add_argument("-p", "--pretty", action='store_true', help="Change to pretty terminal output mode")
    parser.add_argument("-d", "--debug", action='store_true', help="Enable debug logging for troubleshooting")
    # parser.add_argument("--mode", type=str, choices=["cli", "pretty"], help="The output display mode")
    args = parser.parse_args()

    log_format = "%(asctime)s: %(message)s"
    logging.basicConfig(format=log_format, level=logging.INFO,
                        datefmt="%H:%M:%S")
    logging.info(args)

    try:
        run(args.miner_id, args.pretty, args.debug)
        signal.signal(signal.SIGINT, end_script)

        while True:
            if args.pretty:
                miner.paint()
            time.sleep(2)
    except KeyboardInterrupt:
        end_script(None, None)
