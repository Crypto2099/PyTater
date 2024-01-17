import random


class Colors:
    FAIL = '\033[91m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    OKBLUE = '\033[94m'
    HEADER = '\033[95m'
    OKCYAN = '\033[96m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def random_color(block_hash: str):
    seed = zlib.crc32(bytes(block_hash + miner_id, 'ascii'))
    random.seed(seed)
    random_number = random.randint(0, 16777215)
    hex_number = '{0:06X}'.format(random_number)
    return '#' + hex_number